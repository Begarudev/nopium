"""
WebSocket F1 Simulator Server
Real-time race simulation with WebSocket broadcasting
"""

import asyncio
import json
import numpy as np
import random
import math
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Set, Optional
from scipy.interpolate import CubicSpline

# Import simulation logic from nice.py
import sys
import os
sys.path.append(os.path.dirname(__file__))

# Try to import enhanced RaceSim from nice.py
USE_ENHANCED = False
try:
    from nice import RaceSim as EnhancedRaceSim, CarState as EnhancedCarState
    USE_ENHANCED = True
    print("✓ Enhanced RaceSim imported successfully - Enhanced Physics will be used!")
except ImportError as e:
    USE_ENHANCED = False
    print(f"⚠ Warning: Could not import enhanced RaceSim from nice.py: {e}")
    print("   Using basic physics version")

# -------------------- Track & Simulation Core --------------------

TYRE_BASE = {
    'SOFT': 1.00,
    'MEDIUM': 0.95,
    'HARD': 0.90,
    'INTERMEDIATE': 0.82,
    'WET': 0.78,
}

TYRE_WEAR_RATES = {
    'SOFT': 2.0,    # Wears fastest
    'MEDIUM': 1.0,  # Baseline
    'HARD': 0.5,    # Wears slowest
    'INTERMEDIATE': 1.1,  # Slightly faster than medium
    'WET': 1.2      # Slightly faster than medium
}

TYRE_HEAT_FACTORS = {
    'SOFT': 1.2,    # Generates more heat
    'MEDIUM': 1.0,  # Baseline
    'HARD': 0.8,    # Generates less heat
    'INTERMEDIATE': 0.85,  # Less heat generation
    'WET': 0.9      # Less heat generation
}

PIT_TIME_BASE = 22.0  # Base pitstop time in seconds

def get_pitstop_time():
    """
    Generate variable pitstop time with realistic variation.
    Normal variation: ±1 second (using normal distribution, σ=0.5)
    Bad cases: ±2 seconds (5-10% probability)
    Based on real-world F1 data: average ~2.2s service time, but total pit lane time ~20-30s
    """
    # 5-10% chance of bad pitstop (±2 seconds)
    if random.random() < 0.075:  # 7.5% chance
        variation = random.uniform(-2.0, 2.0)
    else:
        # Normal variation: ±1 second using normal distribution
        variation = np.random.normal(0.0, 0.5)
        variation = max(-1.0, min(1.0, variation))  # Clamp to ±1 second
    
    return PIT_TIME_BASE + variation

def load_gp_track_simple():
    """Simplified track for demo - Silverstone-like layout"""
    waypoints = np.array([
        [700.0, 120.0],  # T1  - start/finish, top middle-right
        [550.0, 110.0],  # T2  - slight kink left
        [500.0, 150.0],  # T3
        [400.0, 200.0],  # T4
        [350.0, 300.0],  # T5
        [320.0, 380.0],  # T6
        [280.0, 520.0],  # T7  - bottom-left hairpin
        [500.0, 560.0],  # T8  - long bottom straight

        # --- middle vertical + kink (fixed) ---
        [650.0, 540.0],  # T9  - bottom of central “stick”
        [640.0, 460.0],  # T10 - up a bit
        [610.0, 360.0],  # T11 - further up/left
        [580.0, 280.0],  # T12 - top of the stick
        [650.0, 300.0],  # T13 - kink back to the right

        # --- right-side section ---
        [760.0, 320.0],  # T14
        [840.0, 360.0],  # T15
        [900.0, 350.0],  # T16
        [1000.0, 300.0], # T17 - top-right corner
        [950.0, 200.0],  # T18
        [850.0, 150.0],  # T19
        [700.0, 120.0],  # close loop back to T1
    ], dtype=float)
    return waypoints

def build_spline(waypoints, n_points=2000):
    """Build periodic cubic spline"""
    L = len(waypoints)
    t = np.linspace(0, 1, L)
    xs = waypoints[:, 0]
    ys = waypoints[:, 1]

    csx = CubicSpline(t, xs, bc_type='periodic')
    csy = CubicSpline(t, ys, bc_type='periodic')

    ss = np.linspace(0, 1, n_points)
    dx = csx(ss, 1)
    dy = csy(ss, 1)
    speeds = np.hypot(dx, dy)
    ds = np.gradient(ss) * speeds
    s_arclen = np.cumsum(ds)
    s_arclen = s_arclen - s_arclen[0]
    total_length = s_arclen[-1]

    x1 = csx(ss, 1)
    y1 = csy(ss, 1)
    x2 = csx(ss, 2)
    y2 = csy(ss, 2)
    curvature = np.abs(x1 * y2 - y1 * x2) / (x1 * x1 + y1 * y1 + 1e-9) ** 1.5

    def pos(u):
        return np.vstack([csx(u), csy(u)]).T

    def curv(u):
        return np.interp(u, ss, curvature)

    def s_to_u(arc):
        arc = np.mod(arc, total_length)
        u = np.interp(arc, s_arclen, ss)
        return u

    # Get track boundary for visualization
    track_points = pos(ss)

    return {
        'pos': pos, 
        'curv': curv,
        's_arclen': s_arclen, 
        'total_length': total_length, 
        's_to_u': s_to_u,
        'ss': ss,
        'track_points': track_points.tolist()
    }

class CarState:
    def __init__(self, name, color, driver_skill=0.9, aggression=0.5):
        self.name = name
        self.color = color
        self.driver_skill = driver_skill
        self.aggression = aggression
        self.tyre = 'MEDIUM'
        self.wear = 0.0
        self.fuel = 100.0
        self.laptime = 0.0
        self.total_time = 0.0
        self.laps_completed = 0
        self.on_pit = False
        self.pit_counter = 0.0
        self.s = 0.0
        self.v = 0.0
        self.position = None
        
        # Enhanced physics parameters
        self.engine_rpm = 5000.0
        self.gear = 1
        self.throttle = 0.0
        self.brake_pressure = 0.0
        self.tire_temp = 100.0
        self.tire_pressure = 1.0
        self.aero_downforce = 0.0
        self.drag_coeff = 0.75
        self.yaw_rate = 0.0
        self.slip_angle = 0.0
        self.engine_mode = 'normal'
        self.drs_active = False
        self.ers_energy = 100.0
        
        # Car parameters
        self.mass = 798.0
        self.power_max = 746000.0
        self.brake_bias = 0.6
        self.suspension_stiffness = 50000.0
        self.tire_compound = 'MEDIUM'
        
        # Controller and behavior
        self.lidar = None
        self.controller_type = 'pure_pursuit'
        self.overtaking = False
        self.target_line_offset = 0.0
        
        # Track temperature
        self.track_temp = 25.0
        
        # Pitstop history tracking
        self.pitstop_history = []  # List of dicts: {'lap': int, 'tyre': str, 'undercuts': dict}
        self.pitstop_count = 0
        # Track position and time gaps before pitstop for undercut calculation
        self.position_before_pitstop = None
        self.time_gaps_before_pitstop = {}  # Dict: {car_name: time_gap}

    def to_dict(self, track):
        u = track['s_to_u'](self.s)
        pos = track['pos'](u)[0]
        
        # Calculate heading
        u2 = track['s_to_u'](self.s + 1.0)
        pos2 = track['pos'](u2)[0]
        angle = math.atan2(pos2[1] - pos[1], pos2[0] - pos[0])
        
        return {
            'name': self.name,
            'color': self.color,
            'position': self.position or 0,
            'laps': self.laps_completed,
            'wear': round(self.wear, 3),
            'tyre': self.tyre,
            'fuel': round(self.fuel, 1),
            'speed': round(self.v * 3.6, 1),  # km/h
            'x': float(pos[0]),
            'y': float(pos[1]),
            'angle': float(angle),
            'total_time': round(self.total_time, 2),
            'on_pit': self.on_pit,
            # Enhanced physics parameters
            'rpm': round(getattr(self, 'engine_rpm', 5000), 0),
            'gear': getattr(self, 'gear', 1),
            'throttle': round(getattr(self, 'throttle', 0.0), 2),
            'brake': round(getattr(self, 'brake_pressure', 0.0), 2),
            'tire_temp': round(getattr(self, 'tire_temp', 100.0), 1),
            'drs_active': getattr(self, 'drs_active', False),
            'ers_energy': round(getattr(self, 'ers_energy', 100.0), 1),
            'controller_type': getattr(self, 'controller_type', 'pure_pursuit'),
            'overtaking': getattr(self, 'overtaking', False),
            'aero_downforce': round(getattr(self, 'aero_downforce', 0.0), 0),
            'pitstop_history': getattr(self, 'pitstop_history', []),
            'pitstop_count': getattr(self, 'pitstop_count', 0),
            'time_interval': round(getattr(self, 'time_interval', 0.0), 2),
            'distance_interval': round(getattr(self, 'distance_interval', 0.0), 1),
            'undercut_summary': self._get_undercut_summary()
        }
    
    def _get_undercut_summary(self):
        """Get summary of undercuts for this car's pitstops"""
        summary = []
        for pitstop in getattr(self, 'pitstop_history', []):
            if 'undercuts' in pitstop and pitstop['undercuts']:
                # Find significant undercuts (>1 second gain or loss)
                significant = []
                for other_name, data in pitstop['undercuts'].items():
                    if abs(data['time_gain']) > 1.0:
                        significant.append({
                            'vs': other_name,
                            'time_gain': data['time_gain'],
                            'position_change': data['position_change']
                        })
                if significant:
                    summary.append({
                        'lap': pitstop.get('lap', 0),
                        'undercuts': significant
                    })
        return summary

class RaceSim:
    def __init__(self, track_layout, n_cars=20, weather=None):
        self.track = track_layout
        self.cars = []
        self.dt = 0.5
        self.time = 0.0
        self.weather = weather or {'rain': 0.15, 'track_temp': 25.0, 'wind': 0.0}
        self.total_laps = 36
        self.race_finished = False
        self.race_started = False
        self.init_cars(n_cars)

    def init_cars(self, n):
        driver_names = [
            'Oscar Piastri', 'Lando Norris', 'George Russell', 'Kimi Antonelli',
            'Max Verstappen', 'Yuki Tsunoda', 'Charles Leclerc', 'Lewis Hamilton',
            'Alexander Albon', 'Carlos Sainz', 'Liam Lawson', 'Isack Hadjar',
            'Lance Stroll', 'Fernando Alonso', 'Esteban Ocon', 'Oliver Bearman',
            'Nico Hulkenberg', 'Gabriel Bortoleto', 'Pierre Gasly', 'Franco Colapinto'
        ]
        colors = [
            '#00D2BE', '#0600EF', '#DC0000', '#FF8700', '#DC0000',
            '#0600EF', '#00D2BE', '#006F62', '#FF8700', '#006F62',
            '#1E41FF', '#FF1800', '#00D4AB', '#E10600', '#00665E',
            '#FFB800', '#000000', '#FFFFFF', '#0090FF', '#FF6B00'
        ]
        
        # Initialize tire temperature based on ambient temperature
        ambient_temp = self.weather.get('track_temp', 25.0)
        initial_tire_temp = ambient_temp + 10.0  # Start slightly above ambient
        
        for i in range(n):
            name = driver_names[i % len(driver_names)]
            color = colors[i % len(colors)]
            c = CarState(name, color,
                        driver_skill=0.75 + random.random()*0.25,
                        aggression=0.3 + random.random()*0.7)
            # F1 grid start: all cars start at same position with 2m spacing
            c.s = i * 2.0  # 2 meters between consecutive cars
            c.v = 0.0
            c.tyre = random.choice(['SOFT', 'MEDIUM', 'HARD'])
            c.tire_temp = initial_tire_temp  # Initialize based on ambient temperature
            self.cars.append(c)

    def tyre_grip_coeff(self, car):
        base = TYRE_BASE.get(car.tyre, 0.95)
        grip = base * (1 - 0.6 * car.wear)
        rain = self.weather['rain']
        if car.tyre == 'WET':
            grip *= (1.0 + 0.5 * rain)
        elif car.tyre == 'INTERMEDIATE':
            grip *= (1.0 + 0.3 * rain) if rain > 0.3 else (1.0 - 0.5 * rain)
        else:
            grip *= (1.0 - 0.9 * rain)
        grip *= (0.8 + 0.4 * car.driver_skill)
        return max(grip, 0.05)

    def cornering_speed(self, car, curvature):
        grip = self.tyre_grip_coeff(car)
        k = 12.0
        curv = max(curvature, 1e-6)
        v = math.sqrt(grip * k / curv)
        v *= (1 - 0.001 * car.fuel)
        return v

    def straight_speed(self, car):
        base = 80.0 + 20.0 * car.driver_skill
        base *= (1 - 0.25 * self.weather['rain'])
        # Apply compound speed multiplier directly (SOFT fastest, HARD slowest)
        tyre_speed_multiplier = TYRE_BASE.get(car.tyre, 0.95)
        base *= (0.90 + 0.15 * tyre_speed_multiplier)  # Makes difference more noticeable
        # Also factor in grip coefficient for wear effects
        base *= (0.95 + 0.1 * self.tyre_grip_coeff(car))
        base *= (1 - 0.001 * car.fuel)
        # DRS speed boost: 10% increase when DRS is active
        if getattr(car, 'drs_active', False):
            base *= 1.10
        return base

    def error_probability(self, car):
        rain = self.weather['rain']
        wear = car.wear
        base = 0.0005 + 0.001 * (1 - car.driver_skill)
        prob = base * (1 + 4 * rain + 6 * wear + car.aggression)
        return min(prob, 0.5)

    def pitstop_probability(self, car):
        """
        Calculate pitstop probability based on tyre wear and interval patterns.
        Enhanced logic:
        - Start considering pitstops at 80% wear (low probability ~10-20%)
        - Increase probability significantly at 85% wear
        - Allow stretching to 90% wear if gap behind (>3s) OR fast approaching car (<2s)
        - Force pitstop at 90%+ wear regardless of conditions
        - Analyze interval patterns to time pitstops ending in gaps
        """
        if car.wear < 0.8:
            return 0.0
        
        # Get current leaderboard for interval analysis
        sorted_cars = self.get_leaderboard()
        car_position = next((i for i, c in enumerate(sorted_cars) if c == car), -1)
        
        # Calculate intervals to cars ahead and behind
        gap_behind = None
        gap_ahead = None
        fast_approaching = False
        
        if car_position < len(sorted_cars) - 1:
            car_behind = sorted_cars[car_position + 1]
            track_length = self.track['total_length']
            lap_diff_behind = car_behind.laps_completed - car.laps_completed
            distance_gap_behind = (lap_diff_behind * track_length) + (car.s - car_behind.s)
            if car.v > 0.1:
                gap_behind = distance_gap_behind / car.v
                # Check if car behind is fast approaching (closing gap quickly)
                if gap_behind < 2.0 and gap_behind > 0:
                    fast_approaching = True
        
        if car_position > 0:
            car_ahead = sorted_cars[car_position - 1]
            track_length = self.track['total_length']
            lap_diff_ahead = car.laps_completed - car_ahead.laps_completed
            distance_gap_ahead = (lap_diff_ahead * track_length) + (car_ahead.s - car.s)
            if car.v > 0.1:
                gap_ahead = distance_gap_ahead / car.v
        
        # Base probability based on wear
        if car.wear < 0.85:
            # 80-85%: Low probability (10-20%)
            base_prob = 0.1 + 0.1 * ((car.wear - 0.8) / 0.05)
        elif car.wear < 0.90:
            # 85-90%: Moderate to high probability
            base_prob = 0.2 + 0.6 * ((car.wear - 0.85) / 0.05)
        else:
            # 90%+: Force pitstop
            base_prob = 1.0
        
        # Allow stretching to 90% if good conditions
        if 0.8 <= car.wear < 0.90:
            # Stretch if gap behind (>3 seconds) OR fast approaching car (<2 seconds)
            if gap_behind and gap_behind > 3.0:
                # Large gap behind - can stretch tires
                base_prob *= 0.3  # Reduce probability significantly
            elif fast_approaching:
                # Fast approaching car - pit early to avoid being overtaken
                base_prob *= 1.5  # Increase probability
                base_prob = min(1.0, base_prob)
        
        # Interval pattern analysis: Check if pitstop would end in a gap
        if car.wear >= 0.80:
            # Estimate where car will rejoin after pitstop
            estimated_pit_time = PIT_TIME_BASE + 1.0  # Use average + buffer
            # Estimate track position after pitstop (car continues at current speed during pit)
            estimated_rejoin_s = car.s  # Rejoin at same track position
            estimated_rejoin_time = car.total_time + estimated_pit_time
            
            # Check if there's a gap opportunity (no car within 2-3 seconds)
            gap_opportunity = False
            for other_car in sorted_cars:
                if other_car == car or other_car.on_pit:
                    continue
                
                # Calculate where other car will be when this car rejoins
                time_until_rejoin = estimated_rejoin_time - self.time
                if time_until_rejoin > 0:
                    # Estimate other car's position after time_until_rejoin
                    other_car_future_s = other_car.s + other_car.v * time_until_rejoin
                    track_length = self.track['total_length']
                    
                    # Normalize positions
                    other_car_normalized = (other_car.laps_completed * track_length) + other_car_future_s
                    car_normalized = (car.laps_completed * track_length) + estimated_rejoin_s
                    
                    # Calculate gap
                    gap = abs(other_car_normalized - car_normalized)
                    if car.v > 0.1:
                        time_gap = gap / car.v
                        # If gap is between 2-5 seconds, it's a good opportunity
                        if 2.0 <= time_gap <= 5.0:
                            gap_opportunity = True
                            break
            
            # Increase probability if gap opportunity exists
            if gap_opportunity and car.wear >= 0.85:
                base_prob *= 1.3
                base_prob = min(1.0, base_prob)
        
        # Count how many cars are currently pitting
        cars_in_pit = sum(1 for c in self.cars if c.on_pit)
        
        # Smart pitstop strategy: If 3+ cars are pitting, allow cars to stretch tires
        if cars_in_pit >= 3 and 0.8 <= car.wear < 0.90:
            base_prob *= 0.5
        
        # At critical wear (90%+), always pit regardless of others
        if car.wear >= 0.90:
            base_prob = min(1.0, base_prob)
        
        return base_prob

    def start_race(self):
        """Start the race - allows simulation to proceed"""
        self.race_started = True
    
    def step(self):
        # Only advance simulation if race has started
        if not self.race_started:
            return
        
        # Calculate leaderboard once per step for DRS detection
        sorted_cars = self.get_leaderboard()
        
        for car in self.cars:
            if car.on_pit:
                car.pit_counter -= self.dt
                if car.pit_counter <= 0:
                    car.on_pit = False
                    car.pit_counter = 0
                    # Select tyre based on weather (will be implemented later)
                    rain = self.weather.get('rain', 0.0)
                    if rain > 0.6:
                        car.tyre = 'WET'
                    elif rain > 0.3:
                        car.tyre = 'INTERMEDIATE'
                    else:
                        car.tyre = random.choice(['SOFT', 'MEDIUM', 'HARD'])
                    # Update pitstop history with new tyre
                    if car.pitstop_history:
                        car.pitstop_history[-1]['new_tyre'] = car.tyre
                    # Calculate undercuts for this pitstop
                    self.calculate_undercuts(car)
                    car.wear = 0.0  # Reset wear for new tyres
                    # Reset tire temperature to slightly above ambient (new tyres start warm)
                    ambient_temp = self.weather.get('track_temp', 25.0)
                    car.tire_temp = ambient_temp + 10.0  # New tyres start 10°C above ambient
                    car.position_before_pitstop = None  # Reset (already reset in calculate_undercuts)
                continue
            
            u = self.track['s_to_u'](car.s)
            curv = self.track['curv'](u)
            
            # DRS Detection and Activation (before speed calculations)
            car.drs_active = False
            # Find car position in leaderboard
            car_position = next((i for i, c in enumerate(sorted_cars) if c == car), -1)
            
            # DRS rules: Active after 3 laps by leader, within 1s of car ahead, on straights
            leader = sorted_cars[0] if sorted_cars else None
            if leader and leader.laps_completed >= 3 and car_position > 0:
                car_ahead = sorted_cars[car_position - 1]
                # Calculate time gap to car ahead (positive if car is behind)
                # Use distance-based calculation for accuracy
                track_length = self.track['total_length']
                lap_diff = car.laps_completed - car_ahead.laps_completed
                distance_gap = (lap_diff * track_length) + (car_ahead.s - car.s)
                # Convert distance gap to time gap using current speed
                if car.v > 0.1:
                    time_gap = distance_gap / car.v
                else:
                    time_gap = 999.0  # Very large gap if car is stopped
                # Check if on straight (low curvature)
                is_straight = curv < 0.001
                # DRS active if within 1 second and on straight
                if 0 < time_gap <= 1.0 and is_straight:
                    car.drs_active = True
            
            # Lookahead to anticipate upcoming corners
            lookahead_distance = car.v * 2.0  # Look 2 seconds ahead
            u_ahead = self.track['s_to_u'](car.s + lookahead_distance)
            curv_ahead = self.track['curv'](u_ahead)
            
            v_corner = self.cornering_speed(car, curv)
            v_corner_ahead = self.cornering_speed(car, curv_ahead)
            v_straight = self.straight_speed(car)  # This now includes DRS boost if active
            
            # Use the more restrictive speed limit (current corner or upcoming corner)
            target_v = min(v_straight, v_corner, v_corner_ahead)
            
            # More aggressive braking when exceeding cornering speed
            if car.v > target_v:
                # Brake harder if significantly over speed limit
                speed_excess = car.v - target_v
                if speed_excess > 5.0:
                    car.v -= 20.0 * self.dt  # Hard braking
                else:
                    car.v -= 15.0 * self.dt  # Moderate braking
            elif car.v < target_v:
                # Accelerate only if well below target
                car.v += 6.0 * self.dt
            
            # Cap speed to target_v (respects cornering limits)
            car.v = max(0.0, min(car.v, target_v))

            # Check for pitstop based on probability
            if not car.on_pit and random.random() < self.pitstop_probability(car) * self.dt:
                car.on_pit = True
                # Generate variable pitstop time
                pit_time = get_pitstop_time()
                car.pit_counter = pit_time
                # Record position and time gaps before pitstop for undercut calculation
                sorted_cars = self.get_leaderboard()
                car.position_before_pitstop = car.position
                car.time_gaps_before_pitstop = {}
                for other_car in sorted_cars:
                    if other_car != car:
                        car.time_gaps_before_pitstop[other_car.name] = other_car.total_time - car.total_time
                # Add pit time to total time
                car.total_time += pit_time
                # Record pitstop history
                car.pitstop_count += 1
                car.pitstop_history.append({
                    'lap': car.laps_completed,
                    'tyre': car.tyre,  # Current tyre before pitstop
                    'pit_time': round(pit_time, 2),
                    'undercuts': {}  # Will be populated when pitstop completes
                })

            if random.random() < self.error_probability(car) * self.dt:
                r = random.random()
                if r < 0.6:
                    car.v *= 0.6
                    car.total_time += 2.0
                elif r < 0.9:
                    car.v = 0.0
                    car.total_time += 6.0

            # Tyre wear calculation with compound-specific rates
            base_wear_rate = 0.0005 * (1 + 0.8 * (1 - self.tyre_grip_coeff(car)))
            wear_rate_multiplier = TYRE_WEAR_RATES.get(car.tyre, 1.0)
            # DRS wear penalty: 5% increase when DRS is active
            if getattr(car, 'drs_active', False):
                wear_rate_multiplier *= 1.05
            car.wear += base_wear_rate * wear_rate_multiplier * self.dt
            car.wear = min(car.wear, 0.99)
            
            # Update tire temperature based on speed, cornering, and compound
            ambient_temp = self.weather.get('track_temp', 25.0)
            heat_factor = TYRE_HEAT_FACTORS.get(car.tyre, 1.0)
            # Heat generation from speed and cornering
            slip_angle = abs(curv) * car.v if car.v > 0 else 0
            heat_gen = 0.01 * car.v * slip_angle * heat_factor
            # Cooling based on temperature difference from ambient
            cooling = 0.05 * (car.tire_temp - ambient_temp)
            # Temperature change
            dtemp = (heat_gen - cooling) * self.dt
            car.tire_temp = max(ambient_temp, min(car.tire_temp + dtemp, 150.0))
            
            car.fuel -= 0.02 * self.dt
            if car.fuel < 0:
                car.fuel = 0

            car.s += car.v * self.dt

            L = self.track['total_length']
            if (car.s // L) > ((car.s - car.v * self.dt) // L):
                car.laps_completed += 1
                # Check if race is complete (72 laps)
                if car.laps_completed >= self.total_laps:
                    self.race_finished = True

        self.time += self.dt

    def get_leaderboard(self):
        sorted_cars = sorted(self.cars, 
                           key=lambda c: (-c.laps_completed, -c.s, c.total_time))
        for i, c in enumerate(sorted_cars):
            c.position = i + 1
        return sorted_cars
    
    def calculate_undercuts(self, car):
        """
        Calculate undercut effects for a car that just completed a pitstop.
        Compares position and time gaps before and after pitstop relative to all other cars.
        """
        if not car.pitstop_history or car.position_before_pitstop is None:
            return
        
        # Get current leaderboard
        sorted_cars = self.get_leaderboard()
        current_position = car.position
        
        # Get the most recent pitstop entry
        pitstop_entry = car.pitstop_history[-1]
        
        # Calculate undercuts relative to all other cars
        undercuts = {}
        
        for other_car in sorted_cars:
            if other_car == car:
                continue
            
            # Get time gap before pitstop (stored when entering pit)
            time_gap_before = car.time_gaps_before_pitstop.get(other_car.name, 0.0)
            
            # Calculate time gap after pitstop (current)
            time_gap_after = other_car.total_time - car.total_time
            
            # Calculate position change
            position_change = car.position_before_pitstop - current_position
            
            # Calculate undercut effect (positive = gained time, negative = lost time)
            # If time_gap_after is more negative (or less positive) than before, we gained time
            undercut_time = time_gap_before - time_gap_after
            
            # Store undercut data
            undercuts[other_car.name] = {
                'time_gain': round(undercut_time, 2),
                'position_before': car.position_before_pitstop,
                'position_after': current_position,
                'position_change': position_change,
                'other_position': other_car.position,
                'time_gap_before': round(time_gap_before, 2),
                'time_gap_after': round(time_gap_after, 2)
            }
        
        # Update pitstop history with undercut data
        pitstop_entry['undercuts'] = undercuts
        
        # Reset tracking variables
        car.time_gaps_before_pitstop = {}

    def get_undercut_summary(self):
        """
        Get comprehensive undercut summary for all cars at end of race.
        Returns a list of all pitstops with their undercut effects.
        """
        summary = []
        for car in self.cars:
            for pitstop in car.pitstop_history:
                if 'undercuts' in pitstop and pitstop['undercuts']:
                    # Find significant undercuts (>1 second gain or loss)
                    significant_undercuts = []
                    for other_name, data in pitstop['undercuts'].items():
                        if abs(data['time_gain']) > 1.0:
                            significant_undercuts.append({
                                'vs': other_name,
                                'time_gain': data['time_gain'],
                                'position_change': data['position_change'],
                                'position_before': data['position_before'],
                                'position_after': data['position_after']
                            })
                    if significant_undercuts:
                        summary.append({
                            'car': car.name,
                            'lap': pitstop.get('lap', 0),
                            'pit_time': pitstop.get('pit_time', 0),
                            'old_tyre': pitstop.get('tyre', 'UNKNOWN'),
                            'new_tyre': pitstop.get('new_tyre', 'UNKNOWN'),
                            'undercuts': significant_undercuts
                        })
        return summary
    
    def get_state(self):
        """Get complete race state for WebSocket broadcast"""
        sorted_cars = self.get_leaderboard()
        
        # Calculate intervals (gaps from leader)
        leader = sorted_cars[0] if sorted_cars else None
        if leader:
            for car in sorted_cars:
                # Time interval
                car.time_interval = car.total_time - leader.total_time
                # Distance interval (accounting for lap differences)
                track_length = self.track['total_length']
                lap_diff = car.laps_completed - leader.laps_completed
                distance_interval = (lap_diff * track_length) + (car.s - leader.s)
                car.distance_interval = distance_interval
        
        tyre_counts = {}
        for c in self.cars:
            tyre_counts[c.tyre] = tyre_counts.get(c.tyre, 0) + 1
        
        state = {
            'time': round(self.time, 1),
            'cars': [car.to_dict(self.track) for car in self.cars],
            'weather': self.weather,
            'total_laps': self.total_laps,
            'tyre_distribution': tyre_counts,
            'race_finished': self.race_finished,
            'race_started': self.race_started
        }
        
        # Add undercut summary at end of race
        if self.race_finished:
            state['undercut_summary'] = self.get_undercut_summary()
        
        return state
    
    def reset_race(self):
        """Reset the race for a new race"""
        self.time = 0.0
        self.race_finished = False
        self.race_started = False
        # Reset all cars
        for car in self.cars:
            car.s = 0.0
            car.v = 0.0
            car.laps_completed = 0
            car.total_time = 0.0
            car.wear = 0.0
            car.fuel = 100.0
            car.on_pit = False
            car.pit_counter = 0.0
            car.pitstop_history = []
            car.pitstop_count = 0
            car.position_before_pitstop = None
            car.time_gaps_before_pitstop = {}
            car.tyre = random.choice(['SOFT', 'MEDIUM', 'HARD'])
            ambient_temp = self.weather.get('track_temp', 25.0)
            car.tire_temp = ambient_temp + 10.0
            # F1 grid start: all cars start at same position with 2m spacing
            car_index = self.cars.index(car)
            car.s = car_index * 2.0  # 2 meters between consecutive cars

# -------------------- FastAPI + WebSocket Server --------------------

app = FastAPI(title="F1 Simulator WebSocket Server")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
active_connections: Set[WebSocket] = set()

# Global simulation instance
sim: RaceSim = None
track_data = None

def initialize_simulation(weather=None):
    """Initialize or reset the simulation"""
    global sim, track_data
    waypoints = load_gp_track_simple()
    track_data = build_spline(waypoints, n_points=2000)
    if weather is None:
        weather = {'rain': 0.15, 'track_temp': 22.0, 'wind': 3.0}
    
    if USE_ENHANCED:
        print("🚀 Initializing simulation with Enhanced Physics Engine...")
        sim = EnhancedRaceSim(track_data, n_cars=20, weather=weather)
        # Verify physics engine is loaded
        if hasattr(sim, 'physics_engine') and sim.physics_engine:
            print("✓ Simulation initialized with Enhanced Physics Engine active")
            # Print detailed status if available
            if hasattr(sim, 'get_physics_status'):
                status = sim.get_physics_status()
                if status['enhanced_physics_active']:
                    print("✅ ENHANCED PHYSICS IS ACTIVE AND BEING USED!")
                else:
                    print("⚠ Warning: Enhanced RaceSim loaded but Physics Engine not active")
        else:
            print("⚠ Warning: Enhanced RaceSim loaded but Physics Engine not available")
    else:
        print("⚠ Using basic physics simulation (no enhanced physics)")
        sim = RaceSim(track_data, n_cars=20, weather=weather)
    sim.total_laps = 36

@app.on_event("startup")
async def startup_event():
    """Initialize simulation on server startup"""
    initialize_simulation()
    asyncio.create_task(simulation_loop())

async def simulation_loop():
    """Main simulation loop - runs continuously and broadcasts to all clients"""
    global sim
    while True:
        if sim and len(active_connections) > 0:
            # Check if race is finished and reset if needed
            if sim.race_finished:
                # Wait a moment to show final results, then reset
                await asyncio.sleep(2.0)  # 2 second pause before new race
                sim.reset_race()
            
            # Run multiple simulation steps per broadcast
            for _ in range(3):
                if not sim.race_finished:  # Don't step if race is finished
                    sim.step()
            
            # Get current state
            state = sim.get_state()
            
            # Broadcast to all connected clients
            disconnected = set()
            for connection in active_connections.copy():  # Use copy to avoid modification during iteration
                try:
                    await connection.send_json(state)
                except WebSocketDisconnect:
                    # Client disconnected normally
                    disconnected.add(connection)
                except Exception:
                    # Handle any other connection errors (ClientDisconnected, etc.)
                    disconnected.add(connection)
            
            # Remove disconnected clients
            active_connections.difference_update(disconnected)
        
        await asyncio.sleep(0.1)  # 10 updates per second

@app.get("/")
async def root():
    return {
        "message": "F1 Simulator WebSocket Server",
        "websocket_endpoint": "/ws",
        "track_endpoint": "/api/track"
    }

@app.get("/api/track")
async def get_track():
    """Return track layout data"""
    global track_data
    if track_data is None:
        initialize_simulation()
    return {
        "points": track_data['track_points'] if track_data else [],
        "total_length": float(track_data['total_length']) if track_data else 0.0
    }

@app.post("/api/reset")
async def reset_simulation():
    """Reset the simulation"""
    initialize_simulation()
    return {"message": "Simulation reset"}

class StartRaceRequest(BaseModel):
    rain: float = 0.0
    track_temp: float = 25.0
    wind: float = 0.0

@app.post("/api/start")
async def start_race(request: StartRaceRequest):
    """Start the race with specified weather conditions"""
    global sim
    weather = {
        'rain': max(0.0, min(1.0, request.rain)),
        'track_temp': max(15.0, min(50.0, request.track_temp)),
        'wind': max(0.0, min(20.0, request.wind))
    }
    
    # Initialize or update simulation with new weather
    initialize_simulation(weather=weather)
    
    # Start the race
    if sim:
        sim.start_race()
        return {
            "message": "Race started",
            "weather": weather,
            "race_started": True
        }
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Simulation not initialized")

@app.get("/api/race-status")
async def get_race_status():
    """Get current race status"""
    global sim
    if sim is None:
        return {
            "race_started": False,
            "race_finished": False,
            "time": 0.0
        }
    
    return {
        "race_started": sim.race_started,
        "race_finished": sim.race_finished,
        "time": sim.time,
        "weather": sim.weather,
        "total_laps": sim.total_laps
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    
    try:
        # Ensure simulation is initialized
        if track_data is None:
            initialize_simulation()
        
        # Send initial track data
        if track_data:
            try:
                await websocket.send_json({
                    "type": "track",
                    "data": {
                        "points": track_data['track_points'],
                        "total_length": float(track_data['total_length'])
                    }
                })
            except (WebSocketDisconnect, Exception):
                # Client disconnected before we could send track data
                return
        
        # Keep connection alive
        while True:
            # Receive any messages from client (for future commands)
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get('type') == 'reset':
                    initialize_simulation()
                    
            except WebSocketDisconnect:
                break
            except Exception:
                pass
            
            await asyncio.sleep(0.1)
            
    finally:
        active_connections.discard(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
