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
    def __init__(self, name, color, driver_skill=0.9, car_skill=0.85, aggression=0.5):
        self.name = name
        self.color = color
        self.driver_skill = driver_skill
        self.car_skill = car_skill
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
        # Track position before pitstop for undercut calculation
        self.position_before_pitstop = None
        self.pitstop_lap = None  # Track the lap when current pitstop occurred
        
        # Driver error state tracking
        self.error_active = False
        self.error_timer = 0.0
        self.error_speed_multiplier = 1.0
        
        # Gap/interval tracking (initialized, will be calculated in get_state)
        self.time_interval = 0.0
        self.distance_interval = 0.0
        self.gap_ahead = 0.0
        self.distance_gap_ahead = 0.0

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
            'time_interval': round(getattr(self, 'time_interval', 0.0), 3),
            'distance_interval': round(getattr(self, 'distance_interval', 0.0), 1),
            'gap_ahead': round(getattr(self, 'gap_ahead', 0.0), 3),
            'distance_gap_ahead': round(getattr(self, 'distance_gap_ahead', 0.0), 1),
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
        self.paused = False  # Track pause state separately
        self.speed_multiplier = 1.0  # Simulation speed control
        self.race_events = []  # Track all race events for race log display
        # Track pending undercut battles (only finalized when both drivers have pitted)
        self.pending_undercuts = []  # List of dicts: {'driver_a': name, 'driver_b': name, 'a_pit_lap': lap, 'gap_before': seconds, 'tire_a': compound, 'tire_b': compound, 'a_position': int}
        self.init_cars(n_cars)

    def init_cars(self, n):
        # Driver data: (name, driver_skill, car_skill, color)
        driver_data = [
            ('Max Verstappen', 0.99, 0.86, '#3671C6'),      # Red Bull
            ('Lando Norris', 0.95, 0.90, '#FF8700'),        # McLaren
            ('Oscar Piastri', 0.92, 0.90, '#FF8700'),       # McLaren
            ('Fernando Alonso', 0.92, 0.78, '#00D4AB'),     # Aston Martin
            ('Charles Leclerc', 0.91, 0.87, '#DC0000'),     # Ferrari
            ('George Russell', 0.94, 0.87, '#00665E'),      # Mercedes
            ('Carlos Sainz', 0.89, 0.82, '#DC0000'),        # Ferrari
            ('Lewis Hamilton', 0.88, 0.87, '#006F62'),      # Mercedes
            ('Alexander Albon', 0.85, 0.82, '#0090FF'),     # Williams
            ('Oliver Bearman', 0.84, 0.88, '#E10600'),      # Haas
            ('Isack Hadjar', 0.83, 0.82, '#66ccff'),        # RB
            ('Nico Hulkenberg', 0.82, 0.77, '#66ff66'),     # Sauber
            ('Kimi Antonelli', 0.81, 0.87, '#00665E'),      # Mercedes
            ('Gabriel Bortoleto', 0.80, 0.77, '#66ff66'),   # Sauber
            ('Esteban Ocon', 0.79, 0.82, '#00D4AB'),        # Aston Martin
            ('Pierre Gasly', 0.78, 0.80, '#ff66cf'),        # Alpine
            ('Yuki Tsunoda', 0.77, 0.84, '#3671C6'),        # Red Bull
            ('Liam Lawson', 0.76, 0.85, '#66ccff'),         # RB
            ('Franco Colapinto', 0.75, 0.80, '#ff66cf'),    # Alpine
            ('Lance Stroll', 0.74, 0.78, '#00D4AB')         # Aston Martin
        ]
        
        # Sort drivers by driver_skill descending (highest to lowest)
        driver_data.sort(key=lambda x: x[1], reverse=True)
        
        # Initialize tire temperature based on ambient temperature
        ambient_temp = self.weather.get('track_temp', 25.0)
        initial_tire_temp = max(80.0, ambient_temp + 55.0)  # Start at realistic F1 tire temp (80-90°C)
        
        for i in range(n):
            # Get driver data (cycling through if more cars than drivers)
            driver_info = driver_data[i % len(driver_data)]
            name, driver_skill, car_skill, color = driver_info
            
            c = CarState(name, color,
                        driver_skill=driver_skill,
                        car_skill=car_skill,
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
        # Combine driver skill and car skill for grip handling
        # Driver skill affects how well they handle the car, car skill affects mechanical grip
        combined_skill = 0.7 * car.driver_skill + 0.3 * car.car_skill
        grip *= (0.8 + 0.4 * combined_skill)
        return max(grip, 0.05)

    def cornering_speed(self, car, curvature):
        grip = self.tyre_grip_coeff(car)
        k = 12.0
        curv = max(curvature, 1e-6)
        v = math.sqrt(grip * k / curv)
        v *= (1 - 0.001 * car.fuel)
        # Wind speed penalty: higher wind makes cornering more difficult
        wind_speed = self.weather.get('wind', 0.0)
        wind_penalty_factor = 0.015  # ~1.5% reduction per m/s of wind
        v *= (1 - wind_penalty_factor * wind_speed)
        return v

    def straight_speed(self, car):
        # Combine driver skill and car skill for overall performance
        # Driver skill affects how well they can extract performance from the car
        # Car skill represents the car's inherent speed potential
        combined_skill = 0.6 * car.driver_skill + 0.4 * car.car_skill
        base = 80.0 + 20.0 * combined_skill
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
        """
        Calculate error probability based on driver skill and conditions.
        Higher skill = lower error probability.
        """
        rain = self.weather['rain']
        wear = car.wear
        # Base probability inversely proportional to driver skill
        # Higher skill drivers (0.98) have lower base probability
        # Lower skill drivers (0.68) have higher base probability
        skill_factor = (1 - car.driver_skill)  # 0.02 for Max, 0.32 for Stroll
        base = 0.00005 + 0.0003 * skill_factor  # Further reduced base probability (~60% reduction from original), scales with skill
        
        # Reduce rain factor for wet/inters tyres (they provide better grip in rain)
        # Dry tyres (SOFT/MEDIUM/HARD) keep full rain impact
        if car.tyre in ['WET', 'INTERMEDIATE']:
            rain_factor = 0.3 * rain  # Reduced rain impact for wet tyres
        else:
            rain_factor = 4 * rain  # Full rain impact for dry tyres
        
        prob = base * (1 + rain_factor + 6 * wear + car.aggression)
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
        - Prevent pitstops when less than 3 laps remaining
        """
        # Check if race is almost over - no pitstops if 3 or fewer laps remaining
        laps_remaining = self.total_laps - car.laps_completed
        if laps_remaining <= 3:
            return 0.0
        
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
        self.paused = False
    
    def pause_race(self):
        """Pause the race - stops simulation from proceeding"""
        self.paused = True
    
    def resume_race(self):
        """Resume the race after pausing"""
        self.paused = False
    
    def set_speed(self, speed: float):
        """Set simulation speed multiplier"""
        self.speed_multiplier = max(0.1, min(10.0, speed))  # Clamp between 0.1x and 10x
    
    def step(self):
        # Only advance simulation if race has started and not paused
        if not self.race_started or self.paused:
            return
        
        # Calculate leaderboard once per step for DRS detection
        sorted_cars = self.get_leaderboard()
        
        for car in self.cars:
            if car.on_pit:
                car.pit_counter -= self.dt
                if car.pit_counter <= 0:
                    car.on_pit = False
                    car.pit_counter = 0
                    # Select tyre based on weather and laps remaining
                    rain = self.weather.get('rain', 0.0)
                    laps_remaining = self.total_laps - car.laps_completed
                    if rain > 0.6:
                        car.tyre = 'WET'
                    elif rain > 0.3:
                        car.tyre = 'INTERMEDIATE'
                    else:
                        # Prefer softer compounds when race is ending soon
                        if laps_remaining < 5:
                            car.tyre = 'SOFT'  # Push for fastest lap times
                        elif laps_remaining < 10:
                            car.tyre = random.choice(['SOFT', 'MEDIUM'])  # Prefer softer
                        else:
                            car.tyre = random.choice(['SOFT', 'MEDIUM', 'HARD'])
                    # Update pitstop history with new tyre
                    if car.pitstop_history:
                        car.pitstop_history[-1]['new_tyre'] = car.tyre
                    # Finalize undercut battles where this driver is the second to pit
                    self.finalize_undercut_battles(car)
                    car.wear = 0.0  # Reset wear for new tyres
                    # Reset tire temperature to slightly above ambient (new tyres start warm)
                    ambient_temp = self.weather.get('track_temp', 25.0)
                    car.tire_temp = max(80.0, ambient_temp + 55.0)  # New tyres start at realistic F1 temp
                    car.position_before_pitstop = None  # Reset tracking
                    car.pitstop_lap = None  # Reset pitstop lap tracking
                continue
            
            u = self.track['s_to_u'](car.s)
            curv = self.track['curv'](u)
            
            # DRS Detection and Activation (before speed calculations)
            car.drs_active = False
            # Find car position in leaderboard
            car_position = next((i for i, c in enumerate(sorted_cars) if c == car), -1)
            
            # DRS rules: Active after 3 laps by leader, within 1s of car ahead AND leader, on designated straight only
            leader = sorted_cars[0] if sorted_cars else None
            if leader and leader.laps_completed >= 3 and car_position > 0:
                track_length = self.track['total_length']
                
                # Define DRS zone: specific straight section (e.g., bottom straight from T8 to T9)
                # Using track position normalized to 0-1, DRS zone is roughly 0.35-0.45 of track length
                # This corresponds to the long bottom straight section
                drs_zone_start = 0.35 * track_length
                drs_zone_end = 0.45 * track_length
                
                # Check if car is in DRS zone (accounting for lap wrapping)
                car_s_normalized = car.s % track_length
                in_drs_zone = drs_zone_start <= car_s_normalized <= drs_zone_end
                
                if in_drs_zone:
                    car_ahead = sorted_cars[car_position - 1]
                    # Calculate time gap to car ahead (positive if car is behind)
                    lap_diff = car.laps_completed - car_ahead.laps_completed
                    distance_gap = (lap_diff * track_length) + (car_ahead.s - car.s)
                    # Convert distance gap to time gap using current speed
                    if car.v > 0.1:
                        time_gap_ahead = distance_gap / car.v
                    else:
                        time_gap_ahead = 999.0  # Very large gap if car is stopped
                    
                    # Calculate time gap to leader
                    leader_lap_diff = car.laps_completed - leader.laps_completed
                    leader_distance_gap = (leader_lap_diff * track_length) + (leader.s - car.s)
                    if car.v > 0.1:
                        time_gap_leader = leader_distance_gap / car.v
                    else:
                        time_gap_leader = 999.0
                    
                    # DRS active if within 1 second of car ahead AND within 1 second of leader
                    if 0 < time_gap_ahead <= 1.0 and 0 < time_gap_leader <= 1.0:
                        car.drs_active = True
            
            # Apply defensive behavior: slower cars hold up faster ones
            defensive_speed_multiplier = 1.0
            if not car.on_pit:
                # Use sorted leaderboard to find car directly behind
                car_position = next((i for i, c in enumerate(sorted_cars) if c == car), -1)
                if car_position < len(sorted_cars) - 1:
                    # There's a car behind
                    car_behind = sorted_cars[car_position + 1]
                    if not car_behind.on_pit:
                        track_length = self.track['total_length']
                        
                        # Calculate distance gap (car ahead - car behind)
                        lap_diff = car.laps_completed - car_behind.laps_completed
                        distance_gap = (lap_diff * track_length) + (car.s - car_behind.s)
                        
                        # Normalize to handle lap wrapping
                        if distance_gap < 0:
                            distance_gap += track_length
                        if distance_gap > track_length / 2:
                            distance_gap = track_length - distance_gap
                        
                        # Calculate time gap (how long until car_behind reaches car's position)
                        if car.v > 0.1 and distance_gap > 0:
                            time_gap = distance_gap / car.v
                            
                            # If car behind is within 0.5-3 seconds and on a straight/low-curvature section
                            # Made overtaking more difficult by extending range and increasing reduction
                            if 0.5 <= time_gap <= 3.0 and curv < 0.001:  # Only on straights
                                # Apply speed reduction: closer = more effect (2-8% max, increased from 2-5%)
                                # Scale from 0.98 (at 3s gap) to 0.92 (at 0.5s gap)
                                reduction_factor = 0.98 - (0.06 * (3.0 - time_gap) / 2.5)
                                defensive_speed_multiplier = min(defensive_speed_multiplier, reduction_factor)
            
            # Lookahead to anticipate upcoming corners
            lookahead_distance = car.v * 2.0  # Look 2 seconds ahead
            u_ahead = self.track['s_to_u'](car.s + lookahead_distance)
            curv_ahead = self.track['curv'](u_ahead)
            
            v_corner = self.cornering_speed(car, curv)
            v_corner_ahead = self.cornering_speed(car, curv_ahead)
            v_straight = self.straight_speed(car)  # This now includes DRS boost if active
            
            # Apply defensive speed multiplier
            v_straight *= defensive_speed_multiplier
            
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
            
            # Apply error speed reduction if driver is in error state
            if car.error_active:
                car.v *= car.error_speed_multiplier
                car.error_timer -= self.dt
                if car.error_timer <= 0:
                    # Error state expired, reset
                    car.error_active = False
                    car.error_timer = 0.0
                    car.error_speed_multiplier = 1.0

            # Check for pitstop based on probability
            if not car.on_pit and random.random() < self.pitstop_probability(car) * self.dt:
                car.on_pit = True
                # Generate variable pitstop time
                pit_time = get_pitstop_time()
                car.pit_counter = pit_time
                # Record position before pitstop
                sorted_cars = self.get_leaderboard()
                car.position_before_pitstop = car.position
                car.pitstop_lap = car.laps_completed
                # Check for nearby drivers to create pending undercut battles
                self.check_for_pending_undercuts(car)
                # Add pit time to total time
                car.total_time += pit_time
                # Record pitstop history
                car.pitstop_count += 1
                car.pitstop_history.append({
                    'lap': car.laps_completed,
                    'tyre': car.tyre,  # Current tyre before pitstop
                    'pit_time': round(pit_time, 2),
                    'undercuts': {}  # Will be populated when both drivers have pitted
                })

            # Driver error handling: temporary speed reduction with varying severity
            if not car.error_active and random.random() < self.error_probability(car) * self.dt:
                # Determine error type and severity
                rand_val = random.random()
                if rand_val < 0.40:  # 40% - Lockup (least severe)
                    error_type = "lockup"
                    error_msg = f"{car.name} locks up!"
                    car.error_speed_multiplier = 0.85  # 15% speed reduction
                    car.error_timer = random.uniform(1.5, 2.5)
                    time_loss = random.uniform(0.5, 1.5)
                elif rand_val < 0.75:  # 35% - Goes wide (moderate)
                    error_type = "wide"
                    error_msg = f"{car.name} goes wide!"
                    car.error_speed_multiplier = 0.75  # 25% speed reduction
                    car.error_timer = random.uniform(2.0, 3.5)
                    time_loss = random.uniform(1.0, 2.5)
                elif rand_val < 0.95:  # 20% - Gravel excursion (severe)
                    error_type = "gravel"
                    error_msg = f"{car.name} runs into the gravel!"
                    car.error_speed_multiplier = 0.50  # 50% speed reduction
                    car.error_timer = random.uniform(3.0, 5.0)
                    time_loss = random.uniform(3.0, 6.0)
                else:  # 5% - Spin (most severe)
                    error_type = "spin"
                    error_msg = f"{car.name} spins!"
                    car.error_speed_multiplier = 0.20  # 80% speed reduction
                    car.error_timer = random.uniform(4.0, 7.0)
                    time_loss = random.uniform(5.0, 10.0)
                
                # Trigger error state
                car.error_active = True
                
                # Add time penalty to total_time
                car.total_time += time_loss
                
                # Log error to race events for race log display
                self.race_events.append({
                    'type': 'error',
                    'time': round(self.time, 1),
                    'lap': car.laps_completed,
                    'driver': car.name,
                    'error_type': error_type,
                    'time_loss': round(time_loss, 2),
                    'message': error_msg,
                    'track_position': round(car.s, 1)
                })
                
                # Console log for debugging
                print(f"[Lap {car.laps_completed}] {error_msg} (-{time_loss:.2f}s)")

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
            
            # Determine if car is cornering (high curvature) or on straight (low curvature)
            is_cornering = curv > 0.002  # Threshold for cornering vs straight
            is_straight = curv < 0.0005  # Threshold for straight sections
            
            # Heat generation: much higher during cornering due to lateral forces
            if is_cornering:
                # Cornering generates significant heat from lateral forces
                # Heat scales with speed squared and curvature
                cornering_heat = 2.5 * (car.v ** 2) * curv * heat_factor
                # Additional heat from speed
                speed_heat = 0.3 * car.v * heat_factor
                heat_gen = cornering_heat + speed_heat
            elif is_straight:
                # Straights generate minimal heat (mostly from rolling resistance)
                heat_gen = 0.15 * car.v * heat_factor
            else:
                # Transition zones (medium curvature)
                heat_gen = 0.8 * car.v * abs(curv) * 100 * heat_factor
            
            # Cooling: less aggressive, allows temperature to build up
            # Cooling rate increases with speed (more airflow on straights)
            cooling_rate = 0.02 if is_cornering else 0.08  # Less cooling in corners, more on straights
            
            # Rain increases cooling rate - tyres cool faster in wet conditions
            rain = self.weather.get('rain', 0.0)
            rain_cooling_factor = 1.0 + (rain * 0.5)  # Up to 50% more cooling in heavy rain
            cooling_rate *= rain_cooling_factor
            
            cooling = cooling_rate * (car.tire_temp - ambient_temp) * (1 + car.v * 0.01)
            
            # Additional rain cooling effect - water on track cools tyres more
            if rain > 0:
                rain_cooling = rain * 0.15 * (car.tire_temp - ambient_temp) * self.dt
                cooling += rain_cooling
            
            # Temperature change
            dtemp = (heat_gen - cooling) * self.dt
            car.tire_temp = max(ambient_temp + 20, min(car.tire_temp + dtemp, 150.0))
            
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

        # Calculate intervals after all cars have moved
        sorted_cars = self.get_leaderboard()
        leader = sorted_cars[0] if sorted_cars else None
        if leader:
            track_length = self.track['total_length']
            for car in sorted_cars:
                # Time interval
                car.time_interval = car.total_time - leader.total_time
                # Distance interval (accounting for lap differences)
                lap_diff = car.laps_completed - leader.laps_completed
                distance_interval = (lap_diff * track_length) + (car.s - leader.s)
                car.distance_interval = distance_interval

        self.time += self.dt

    def get_leaderboard(self):
        sorted_cars = sorted(self.cars, 
                           key=lambda c: (-c.laps_completed, -c.s, c.total_time))
        for i, c in enumerate(sorted_cars):
            c.position = i + 1
        return sorted_cars
    
    def check_for_pending_undercuts(self, car):
        """
        Check for nearby drivers when a car enters the pits and create pending undercut entries.
        F1 Expert Logic: Only tracks strategic undercut opportunities when:
        - Drivers are racing closely (within 5 seconds, not 10)
        - They're fighting for position (adjacent or within 2 positions)
        - Both are on similar tire compounds/wear (strategic battle)
        - The other driver hasn't pitted yet
        """
        sorted_cars = self.get_leaderboard()
        current_lap = car.laps_completed
        current_tire = car.tyre
        
        # Clean up any old pending undercuts where this car is driver_a (they're pitting again)
        # Remove in reverse order to avoid index shifting
        indices_to_remove = []
        for i, pending in enumerate(self.pending_undercuts):
            if pending['driver_a'] == car.name:
                indices_to_remove.append(i)
        for idx in reversed(indices_to_remove):
            self.pending_undercuts.pop(idx)
        
        # Check for strategic undercut opportunities (F1 expert criteria)
        for other_car in sorted_cars:
            if other_car == car or other_car.on_pit:
                continue
            
            # Calculate time gap to this other car
            time_gap = other_car.total_time - car.total_time
            
            # F1 Expert Criteria for undercut:
            # 1. Racing closely (within 5 seconds - tighter than before)
            # 2. Fighting for position (adjacent positions or within 2 positions)
            # 3. Same lap (not lapped)
            # 4. Similar tire compounds (strategic battle, not just random gap)
            position_diff = abs(car.position - other_car.position)
            is_adjacent = position_diff <= 2  # Adjacent or within 2 positions
            
            # Check if they're on similar tire compounds (both on same compound type)
            tire_types_match = (current_tire == other_car.tyre) or \
                              (current_tire in ['SOFT', 'MEDIUM', 'HARD'] and 
                               other_car.tyre in ['SOFT', 'MEDIUM', 'HARD'])
            
            # Only create pending undercut if:
            # 1. They're racing closely (within 5 seconds - strategic window)
            # 2. Fighting for position (adjacent or within 2 positions)
            # 3. Same lap
            # 4. Similar tire compounds (strategic battle)
            if (abs(time_gap) <= 5.0 and 
                abs(other_car.laps_completed - current_lap) == 0 and
                is_adjacent and
                tire_types_match):
                
                # Check if this battle already exists (avoid duplicates)
                battle_exists = False
                for pending in self.pending_undercuts:
                    if (pending['driver_a'] == car.name and pending['driver_b'] == other_car.name) or \
                       (pending['driver_a'] == other_car.name and pending['driver_b'] == car.name):
                        battle_exists = True
                        break
                
                if not battle_exists:
                    # Create pending undercut entry
                    # driver_a is the one pitting first (attempting undercut)
                    self.pending_undercuts.append({
                        'driver_a': car.name,
                        'driver_b': other_car.name,
                        'a_pit_lap': current_lap,
                        'gap_before': round(time_gap, 2),  # Gap from A's perspective (B - A)
                        'tire_a': current_tire,
                        'tire_b': other_car.tyre,
                        'a_position': car.position,
                        'b_position': other_car.position
                    })
    
    def finalize_undercut_battles(self, car):
        """
        Finalize undercut calculations when the second driver completes their pitstop.
        Compares time gap after both have pitted vs. gap before first pitted.
        Positive value = first driver (A) gained advantage, negative = second driver (B) gained advantage.
        """
        sorted_cars = self.get_leaderboard()
        current_lap = car.laps_completed
        current_tire = car.tyre
        
        # Find all pending undercuts where this car is driver_b (second to pit)
        battles_to_finalize = []
        for i, pending in enumerate(self.pending_undercuts):
            if pending['driver_b'] == car.name:
                battles_to_finalize.append((i, pending))
        
        # Process each battle (iterate in reverse to avoid index shifting when removing)
        battles_to_finalize.reverse()
        for idx, pending in battles_to_finalize:
            driver_a_name = pending['driver_a']
            driver_b_name = pending['driver_b']
            
            # Find the actual car objects
            driver_a = next((c for c in sorted_cars if c.name == driver_a_name), None)
            driver_b = next((c for c in sorted_cars if c.name == driver_b_name), None)
            
            if not driver_a or not driver_b:
                # Remove invalid battle
                self.pending_undercuts.pop(idx)
                continue
            
            # Calculate time gap after both have pitted
            # Gap from A's perspective: B.total_time - A.total_time
            gap_after = driver_b.total_time - driver_a.total_time
            gap_before = pending['gap_before']
            
            # Calculate undercut advantage
            # Positive = A gained time (undercut successful)
            # Negative = B gained time (defended/overcut successful)
            undercut_time = gap_before - gap_after
            
            # F1 Expert Logic: Only record undercuts with meaningful strategic impact (>1 second)
            # This ensures we only show actual strategic battles, not minor timing differences
            if abs(undercut_time) < 1.0:
                # Not significant enough - remove from pending without storing
                self.pending_undercuts.pop(idx)
                continue
            
            # Get tire compound advantage factor
            tire_a = pending['tire_a']
            tire_b = current_tire  # B's new tire after pitstop
            
            # Tire performance multipliers (from TYRE_BASE)
            tire_perf_a = TYRE_BASE.get(tire_a, 0.90)
            tire_perf_b = TYRE_BASE.get(tire_b, 0.90)
            tire_factor = tire_perf_b - tire_perf_a  # Positive if B has better tires
            
            # Get current positions
            position_a = driver_a.position
            position_b = driver_b.position
            
            # Calculate position change for both drivers
            position_change_a = pending['a_position'] - position_a
            position_change_b = pending['b_position'] - position_b
            
            # F1 Expert Logic: Only store undercut from the strategic perspective
            # If A successfully undercuts B (A gains time), show it for A as success
            # If B gets undercut (A gains time), show it for B as failure
            # We store for both but filter in get_undercut_summary to show appropriately
            
            # Store for Driver A (the one who attempted the undercut)
            for pitstop in driver_a.pitstop_history:
                if pitstop.get('lap') == pending['a_pit_lap']:
                    if 'undercuts' not in pitstop:
                        pitstop['undercuts'] = {}
                    pitstop['undercuts'][driver_b_name] = {
                        'time_gain': round(undercut_time, 2),  # From A's perspective
                        'position_before': pending['a_position'],
                        'position_after': position_a,
                        'position_change': position_change_a,
                        'other_position': position_b,
                        'time_gap_before': round(gap_before, 2),
                        'time_gap_after': round(gap_after, 2),
                        'tire_a': tire_a,
                        'tire_b': tire_b,
                        'tire_factor': round(tire_factor, 3),
                        'undercut_type': 'success' if undercut_time > 0 else 'failed'  # A's perspective
                    }
                    break
            
            # Store for Driver B (the one who got undercut or defended)
            # Use the most recent pitstop entry (driver B just exited the pit)
            if driver_b.pitstop_history:
                pitstop = driver_b.pitstop_history[-1]
                if 'undercuts' not in pitstop:
                    pitstop['undercuts'] = {}
                pitstop['undercuts'][driver_a_name] = {
                    'time_gain': round(-undercut_time, 2),  # From B's perspective (inverted)
                    'position_before': pending['b_position'],
                    'position_after': position_b,
                    'position_change': position_change_b,
                    'other_position': position_a,
                    'time_gap_before': round(-gap_before, 2),  # Inverted from B's perspective
                    'time_gap_after': round(-gap_after, 2),  # Inverted from B's perspective
                    'tire_a': tire_b,
                    'tire_b': tire_a,
                    'tire_factor': round(-tire_factor, 3),
                    'undercut_type': 'undercut' if undercut_time > 0 else 'defended'  # B's perspective
                }
            
            # Remove finalized battle from pending list
            self.pending_undercuts.pop(idx)

    def get_undercut_summary(self):
        """
        Get comprehensive undercut summary for all cars at end of race.
        F1 Expert Logic: Only shows meaningful strategic undercuts:
        - Drivers were racing closely (within 5s before first pit)
        - Significant strategic impact (>1s gain/loss)
        - Shows from perspective of who gained (successful undercut) or lost (got undercut)
        - Prevents showing same battle twice
        """
        summary = []
        # Track which undercut battles we've already included (avoid duplicates)
        # Key: tuple(sorted driver names), Value: which driver's perspective to show
        included_battles = {}
        
        # First pass: collect all potential undercuts
        potential_undercuts = []
        for car in self.cars:
            for pitstop in car.pitstop_history:
                if 'undercuts' in pitstop and pitstop['undercuts']:
                    for other_name, data in pitstop['undercuts'].items():
                        gap_before = abs(data.get('time_gap_before', 999))
                        time_gain = data.get('time_gain', 0)
                        undercut_type = data.get('undercut_type', '')
                        
                        # Only consider meaningful strategic battles
                        if gap_before <= 5.0 and abs(time_gain) > 1.0:
                            battle_id = tuple(sorted([car.name, other_name]))
                            potential_undercuts.append({
                                'battle_id': battle_id,
                                'driver': car.name,
                                'other': other_name,
                                'pitstop': pitstop,
                                'data': data,
                                'time_gain': time_gain,
                                'undercut_type': undercut_type
                            })
        
        # Second pass: decide which perspective to show (prefer showing from winner/loser perspective)
        for undercut in potential_undercuts:
            battle_id = undercut['battle_id']
            
            # If we haven't seen this battle, decide which perspective to show
            if battle_id not in included_battles:
                # Prefer showing from perspective of:
                # 1. Driver who successfully undercut (positive time_gain)
                # 2. Driver who got undercut (negative time_gain from their perspective)
                # This ensures we show strategic outcomes, not just timing differences
                
                # Find both perspectives of this battle
                perspectives = [u for u in potential_undercuts if u['battle_id'] == battle_id]
                
                # Choose the perspective with the most strategic meaning
                # If someone successfully undercut (positive gain), show from their perspective
                # If someone got undercut (negative gain), show from their perspective
                best_perspective = None
                for p in perspectives:
                    if p['time_gain'] > 0:  # Successful undercut
                        best_perspective = p
                        break
                    elif p['time_gain'] < 0:  # Got undercut
                        if best_perspective is None or best_perspective['time_gain'] > p['time_gain']:
                            best_perspective = p
                
                if best_perspective:
                    included_battles[battle_id] = best_perspective['driver']
        
        # Third pass: build summary from chosen perspectives
        for car in self.cars:
            for pitstop in car.pitstop_history:
                if 'undercuts' in pitstop and pitstop['undercuts']:
                    significant_undercuts = []
                    for other_name, data in pitstop['undercuts'].items():
                        battle_id = tuple(sorted([car.name, other_name]))
                        
                        # Only include if this is the chosen perspective for this battle
                        if battle_id in included_battles and included_battles[battle_id] == car.name:
                            gap_before = abs(data.get('time_gap_before', 999))
                            time_gain = data.get('time_gain', 0)
                            
                            if gap_before <= 5.0 and abs(time_gain) > 1.0:
                                significant_undercuts.append({
                                    'vs': other_name,
                                    'time_gain': time_gain,
                                    'position_change': data.get('position_change', 0),
                                    'position_before': data.get('position_before', 0),
                                    'position_after': data.get('position_after', 0),
                                    'tire_a': data.get('tire_a', 'UNKNOWN'),
                                    'tire_b': data.get('tire_b', 'UNKNOWN'),
                                    'undercut_type': data.get('undercut_type', '')
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
    
    def get_race_insights(self):
        """
        Generate actionable race insights for each driver.
        Returns driver-wise insights including undercuts, pit strategies, and recommendations.
        Insights are ordered by final position (P1, P2, etc.).
        """
        insights = {}
        sorted_cars = self.get_leaderboard()
        
        # Process cars in position order (P1, P2, etc.) to maintain order in dict
        for car in sorted_cars:
            driver_insights = {
                'name': car.name,
                'final_position': car.position,
                'total_time': car.total_time,
                'pitstops': len(car.pitstop_history),
                'insights': [],
                'recommendations': []
            }
            
            # Analyze pitstop strategy
            if car.pitstop_history:
                pitstop_count = len(car.pitstop_history)
                # Check for undercut opportunities
                best_undercut = None
                worst_undercut = None
                best_gain = -999
                worst_loss = 999
                
                for pitstop in car.pitstop_history:
                    if 'undercuts' in pitstop:
                        for other_name, data in pitstop['undercuts'].items():
                            gain = data.get('time_gain', 0)
                            if gain > best_gain:
                                best_gain = gain
                                best_undercut = {
                                    'lap': pitstop.get('lap', 0),
                                    'vs': other_name,
                                    'gain': round(gain, 2),
                                    'position_change': data.get('position_change', 0)
                                }
                            if gain < worst_loss:
                                worst_loss = gain
                                worst_undercut = {
                                    'lap': pitstop.get('lap', 0),
                                    'vs': other_name,
                                    'loss': round(abs(gain), 2),
                                    'position_change': data.get('position_change', 0)
                                }
                
                if best_undercut and best_gain > 1.0:
                    driver_insights['insights'].append({
                        'type': 'undercut_success',
                        'message': f"Best undercut: Gained {best_undercut['gain']}s vs {best_undercut['vs']} on lap {best_undercut['lap']}",
                        'action': f"Pitstop timing on lap {best_undercut['lap']} was excellent - consider similar timing in future races"
                    })
                
                if worst_undercut and worst_loss < -1.0:
                    driver_insights['insights'].append({
                        'type': 'undercut_failure',
                        'message': f"Lost {worst_undercut['loss']}s vs {worst_undercut['vs']} on lap {worst_undercut['lap']}",
                        'action': f"Pitstop timing on lap {worst_undercut['lap']} was suboptimal - consider pitting earlier or later next time"
                    })
                
                # Analyze pitstop frequency
                if pitstop_count == 0:
                    driver_insights['recommendations'].append("Consider a pitstop strategy - no stops may have cost time")
                elif pitstop_count > 2:
                    driver_insights['recommendations'].append(f"Multiple pitstops ({pitstop_count}) - consider optimizing strategy to reduce stops")
                
                # Analyze tyre choices
                tyre_choices = [p.get('new_tyre', 'UNKNOWN') for p in car.pitstop_history if 'new_tyre' in p]
                if tyre_choices:
                    rain = self.weather.get('rain', 0)
                    if rain > 0.3 and 'WET' not in tyre_choices and 'INTERMEDIATE' not in tyre_choices:
                        driver_insights['recommendations'].append("Consider using wet/inters tyres in rainy conditions")
            
            # Analyze final position vs starting position
            if car.position:
                # Assuming starting position is based on car index (simplified)
                starting_pos = self.cars.index(car) + 1
                position_change = starting_pos - car.position
                if position_change > 0:
                    driver_insights['insights'].append({
                        'type': 'position_gain',
                        'message': f"Gained {position_change} positions (P{starting_pos} → P{car.position})",
                        'action': "Strong race performance - maintain consistency"
                    })
                elif position_change < 0:
                    driver_insights['insights'].append({
                        'type': 'position_loss',
                        'message': f"Lost {abs(position_change)} positions (P{starting_pos} → P{car.position})",
                        'action': "Review race strategy and pitstop timing for improvement"
                    })
            
            insights[car.name] = driver_insights
        
        return insights
    
    def _extract_driver_data_for_insights(self, car):
        """
        Extract and format driver data for ML insights generation.
        
        Args:
            car: CarState object
            
        Returns:
            Dictionary with formatted driver data
        """
        # Extract pitstop strategy from pitstop_history
        pitstop_strategy = []
        for pitstop in car.pitstop_history:
            pitstop_strategy.append({
                'lap': pitstop.get('lap', 0),
                'old_tyre': pitstop.get('tyre', 'UNKNOWN'),
                'new_tyre': pitstop.get('new_tyre', 'UNKNOWN')
            })
        
        # Calculate tire usage counts
        tire_usage = {}
        if car.pitstop_history:
            # Count laps on starting tire (from lap 0 to first pitstop)
            first_pitstop_lap = car.pitstop_history[0].get('lap', 0)
            starting_tyre = car.pitstop_history[0].get('tyre', car.tyre)
            if starting_tyre:
                tire_usage[starting_tyre] = tire_usage.get(starting_tyre, 0) + first_pitstop_lap
            
            # Count laps on tires between pitstops
            for i in range(len(car.pitstop_history)):
                pitstop = car.pitstop_history[i]
                new_tyre = pitstop.get('new_tyre', car.tyre)
                current_lap = pitstop.get('lap', 0)
                
                # Determine end lap (next pitstop or race end)
                if i < len(car.pitstop_history) - 1:
                    next_lap = car.pitstop_history[i + 1].get('lap', car.laps_completed)
                    laps_on_this_tyre = next_lap - current_lap
                else:
                    # Last pitstop, count to race end
                    laps_on_this_tyre = car.laps_completed - current_lap
                
                if new_tyre and laps_on_this_tyre > 0:
                    tire_usage[new_tyre] = tire_usage.get(new_tyre, 0) + laps_on_this_tyre
        else:
            # No pitstops, all laps on starting tire
            tire_usage[car.tyre] = car.laps_completed
        
        # Extract undercut battles from pitstop history
        undercut_battles = []
        for pitstop in car.pitstop_history:
            if 'undercuts' in pitstop and pitstop['undercuts']:
                for other_name, data in pitstop['undercuts'].items():
                    undercut_battles.append({
                        'lap': pitstop.get('lap', 0),
                        'vs': other_name,
                        'time_gain': data.get('time_gain', 0),
                        'undercut_type': data.get('undercut_type', ''),
                        'tire_a': data.get('tire_a', ''),
                        'tire_b': data.get('tire_b', ''),
                        'position_before': data.get('position_before', 0),
                        'position_after': data.get('position_after', 0),
                        'position_change': data.get('position_change', 0),
                        'time_gap_before': data.get('time_gap_before', 0),
                        'time_gap_after': data.get('time_gap_after', 0)
                    })
        
        return {
            'name': car.name,
            'final_position': car.position or 0,
            'total_time': car.total_time,
            'laps_completed': car.laps_completed,
            'pitstop_count': len(car.pitstop_history),
            'pitstop_strategy': pitstop_strategy,
            'tire_usage': tire_usage,
            'undercut_battles': undercut_battles,
            'fastest_lap': {},  # Not tracked in current simulation
            'sector_performance': {},  # Not tracked in current simulation
            'race_events': []  # Not tracked per driver in current simulation
        }
    
    def get_state(self):
        """Get complete race state for WebSocket broadcast"""
        sorted_cars = self.get_leaderboard()
        
        # Calculate intervals (gaps from leader and car ahead)
        leader = sorted_cars[0] if sorted_cars else None
        if leader:
            for i, car in enumerate(sorted_cars):
                # Time interval from leader
                car.time_interval = max(0.0, car.total_time - leader.total_time)
                
                # Distance interval from leader (accounting for lap differences)
                track_length = self.track['total_length']
                lap_diff = car.laps_completed - leader.laps_completed
                distance_interval = (lap_diff * track_length) + (car.s - leader.s)
                car.distance_interval = distance_interval
                
                # Calculate gap to car ahead (for better display)
                if i > 0:
                    car_ahead = sorted_cars[i - 1]
                    # Time gap to car ahead
                    car.gap_ahead = max(0.0, car.total_time - car_ahead.total_time)
                    # Distance gap to car ahead
                    lap_diff_ahead = car.laps_completed - car_ahead.laps_completed
                    distance_gap_ahead = (lap_diff_ahead * track_length) + (car_ahead.s - car.s)
                    car.distance_gap_ahead = distance_gap_ahead
                else:
                    # Leader has no car ahead
                    car.gap_ahead = 0.0
                    car.distance_gap_ahead = 0.0
        
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
            'race_started': self.race_started,
            'paused': self.paused,
            'speed_multiplier': self.speed_multiplier,
            'race_events': self.race_events  # Include race events for race log display
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
        self.paused = False
        self.speed_multiplier = 1.0
        self.race_events = []  # Clear race events
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
            car.pitstop_lap = None
            car.tyre = random.choice(['SOFT', 'MEDIUM', 'HARD'])
            ambient_temp = self.weather.get('track_temp', 25.0)
            car.tire_temp = max(80.0, ambient_temp + 55.0)  # Reset to realistic F1 tire temp
            # Reset error state
            car.error_active = False
            car.error_timer = 0.0
            car.error_speed_multiplier = 1.0
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
            # Don't auto-reset after race finish - keep showing final results
            # Race reset will be handled manually via reset button in frontend
            
            # Run multiple simulation steps per broadcast, adjusted by speed multiplier
            steps_per_broadcast = max(1, int(3 * sim.speed_multiplier))
            for _ in range(steps_per_broadcast):
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

@app.post("/api/pause")
async def pause_race():
    """Pause the race (legacy endpoint)"""
    global sim
    if sim is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Simulation not initialized")
    
    sim.pause_race()
    return {
        "message": "Race paused",
        "race_started": False
    }

@app.post("/api/simulation/pause")
async def pause_simulation():
    """Pause the simulation"""
    global sim
    if sim is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Simulation not initialized")
    
    sim.pause_race()
    return {
        "message": "Simulation paused",
        "paused": sim.paused,
        "race_started": sim.race_started
    }

@app.post("/api/simulation/resume")
async def resume_simulation():
    """Resume the simulation"""
    global sim
    if sim is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Simulation not initialized")
    
    sim.resume_race()
    return {
        "message": "Simulation resumed",
        "paused": sim.paused,
        "race_started": sim.race_started
    }

class SpeedRequest(BaseModel):
    speed: float

@app.post("/api/simulation/speed")
async def set_simulation_speed(request: SpeedRequest):
    """Set simulation speed multiplier"""
    global sim
    if sim is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Simulation not initialized")
    
    sim.set_speed(request.speed)
    return {
        "message": f"Simulation speed set to {sim.speed_multiplier}x",
        "speed_multiplier": sim.speed_multiplier
    }

@app.get("/api/race-status")
async def get_race_status():
    """Get current race status"""
    global sim
    if sim is None:
        return {
            "race_started": False,
            "race_finished": False,
            "paused": False,
            "speed_multiplier": 1.0,
            "time": 0.0
        }
    
    return {
        "race_started": sim.race_started,
        "race_finished": sim.race_finished,
        "paused": sim.paused,
        "speed_multiplier": sim.speed_multiplier,
        "time": sim.time,
        "weather": sim.weather,
        "total_laps": sim.total_laps
    }

@app.get("/api/race-insights")
async def get_race_insights():
    """Get actionable race insights for all drivers"""
    global sim
    if sim is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Simulation not initialized")
    
    if not sim.race_finished:
        return {
            "message": "Race not finished yet",
            "insights": {}
        }
    
    insights = sim.get_race_insights()
    return {
        "insights": insights,
        "race_finished": True
    }

@app.post("/api/driver-insight/{driver_name}")
async def generate_driver_insight(driver_name: str):
    """Generate ML-style insights for a single driver using Gemini"""
    global sim
    from fastapi import HTTPException
    from insights_generator import InsightsGenerator
    
    if sim is None:
        raise HTTPException(status_code=500, detail="Simulation not initialized")
    
    if not sim.race_finished:
        raise HTTPException(status_code=400, detail="Race not finished yet")
    
    # Find the driver
    driver_car = None
    for car in sim.cars:
        if car.name == driver_name:
            driver_car = car
            break
    
    if not driver_car:
        raise HTTPException(status_code=404, detail=f"Driver {driver_name} not found")
    
    # Extract driver data
    driver_data = sim._extract_driver_data_for_insights(driver_car)
    
    # Build race summary
    sorted_cars = sim.get_leaderboard()
    winner = sorted_cars[0].name if sorted_cars else 'Unknown'
    
    race_summary = {
        'total_laps': sim.total_laps,
        'race_duration': sim.time,
        'weather': sim.weather,
        'track_length': sim.track['total_length'],
        'winner': winner,
        'fastest_lap_overall': 'N/A'  # Not tracked
    }
    
    # Create single-driver race data
    single_driver_race_data = {
        'race_summary': race_summary,
        'drivers': [driver_data]
    }
    
    # Generate insights
    try:
        generator = InsightsGenerator()
        insights = generator.generate_single_driver_insights(single_driver_race_data, driver_name)
        
        return {
            'driver_name': driver_name,
            'insights': insights,
            'success': True
        }
    except Exception as e:
        print(f"[API] Error generating insights for {driver_name}: {str(e)}")
        return {
            'driver_name': driver_name,
            'insights': {},
            'success': False,
            'error': str(e)
        }

@app.get("/api/optimal-pit-strategy")
async def get_optimal_pit_strategy():
    """
    Generate optimal pit strategy recommendations based on race undercut analysis.
    Uses Gemini 2.5 Flash to analyze successful undercuts and recommend pit windows.
    """
    global sim
    from fastapi import HTTPException
    from insights_generator import InsightsGenerator
    
    if sim is None:
        raise HTTPException(status_code=500, detail="Simulation not initialized")
    
    if not sim.race_finished:
        raise HTTPException(status_code=400, detail="Race not finished yet")
    
    # Extract race data for all drivers
    drivers_data = []
    sorted_cars = sim.get_leaderboard()
    winner = sorted_cars[0].name if sorted_cars else 'Unknown'
    
    for car in sorted_cars:
        driver_data = sim._extract_driver_data_for_insights(car)
        drivers_data.append(driver_data)
    
    race_summary = {
        'total_laps': sim.total_laps,
        'race_duration': sim.time,
        'weather': sim.weather,
        'track_length': sim.track['total_length'],
        'winner': winner,
        'fastest_lap_overall': 'N/A'  # Not tracked
    }
    
    race_data = {
        'race_summary': race_summary,
        'drivers': drivers_data
    }
    
    # Generate optimal pit strategy
    try:
        generator = InsightsGenerator()
        strategy = generator.generate_optimal_pit_strategy(race_data)
        
        return {
            'success': True,
            'strategy': strategy
        }
    except Exception as e:
        print(f"[API] Error generating optimal pit strategy: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'strategy': {
                'one_stop_strategy': {},
                'two_stop_strategy': {},
                'key_insights': []
            }
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
