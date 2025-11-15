# Colab-ready 2D F1 Simulator + Live Dashboard
# Filename: colab_f1_simulator.py
# Run in Google Colab (or local Jupyter). This is a single-file prototype that:
# - Loads a non-oval Grand Prix track (attempts to use fastf1; falls back to embedded Silverstone-like waypoints)
# - Builds a spline centerline and computes curvature
# - Simulates multiple cars on the track with weather, tyre compound, driver form
# - Renders a large dashboard: big track view + large live leaderboard + telemetry

# --- Install required packages (Colab) ---
# Uncomment the pip line in Colab if packages aren't installed
# !pip install numpy matplotlib scipy shapely fastf1 tqdm

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.animation import FuncAnimation
from scipy.interpolate import CubicSpline
from shapely.geometry import Point, Polygon
import random
import math
import time
from tqdm.notebook import tqdm

# -------------------- Track loader --------------------
# Try loading circuit track from fastf1 (if installed). If not available, use fallback waypoints.

USE_FASTF1 = True
try:
    import fastf1
    from fastf1 import plotting
    fastf1.Cache.enable_cache('./fastf1_cache')
except Exception as e:
    USE_FASTF1 = False


def load_gp_track(circuit_name='Silverstone', session_year=2023):
    """Attempt to load track centerline waypoints using fastf1. If fail, return fallback waypoints.
    circuit_name: name recognized by fastf1 (e.g., 'Silverstone').
    """
    if USE_FASTF1:
        try:
            # fastf1 provides a layout module (fastf1.plotting) that has track data
            from fastf1 import plotting
            layout = plotting.get_circuit_layout(circuit_name)
            waypoints = np.vstack([layout['X'], layout['Y']]).T
            # fastf1 returns arrays - ensure closed loop
            if not np.allclose(waypoints[0], waypoints[-1]):
                waypoints = np.vstack([waypoints, waypoints[0]])
            print(f"Loaded track '{circuit_name}' via fastf1 with {len(waypoints)} waypoints")
            return waypoints
        except Exception as ex:
            print('fastf1 load failed:', ex)
            print('Falling back to built-in waypoint set')

    # Fallback: simplified Silverstone-like layout (not to scale) - non-oval GP shape
    waypoints = np.array([
        [0, 0], [250, 20], [500, 50], [650, 200], [700, 420], [600, 600],
        [400, 650], [200, 600], [100, 450], [120, 300], [60, 150], [0, 0]
    ], dtype=float)
    print('Using fallback track with', len(waypoints), 'waypoints')
    return waypoints

# -------------------- Spline & geometry tools --------------------

def build_spline(waypoints, n_points=4000):
    """Build periodic cubic spline parametrized by s in [0,1)
    Returns functions pos(s) -> (x,y) and curvature(s)
    Also returns arclength sampled arrays for mapping distance -> s
    """
    # Parameter t along waypoints
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
    # approximate arclength
    ds = np.gradient(ss) * speeds
    s_arclen = np.cumsum(ds)
    s_arclen = s_arclen - s_arclen[0]
    total_length = s_arclen[-1]

    # curvature magnitude = |x'y'' - y'x''| / (x'^2 + y'^2)^(3/2)
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
        # arc in [0, total_length] -> parameter u in [0,1]
        arc = np.mod(arc, total_length)
        u = np.interp(arc, s_arclen, ss)
        return u

    return {
        'csx': csx, 'csy': csy, 'pos': pos, 'curv': curv,
        's_arclen': s_arclen, 'total_length': total_length, 's_to_u': s_to_u,
        'ss': ss
    }

# -------------------- Simulation models --------------------

TYRE_BASE = {
    'SOFT': 1.00,
    'MEDIUM': 0.95,
    'HARD': 0.90,
    'WET': 0.78,
}

TYRE_WEAR_RATES = {
    'SOFT': 2.0,    # Wears fastest
    'MEDIUM': 1.0,  # Baseline
    'HARD': 0.5,    # Wears slowest
    'WET': 1.2      # Slightly faster than medium
}

TYRE_HEAT_FACTORS = {
    'SOFT': 1.2,    # Generates more heat
    'MEDIUM': 1.0,  # Baseline
    'HARD': 0.8,    # Generates less heat
    'WET': 0.9      # Less heat generation
}

PIT_TIME = 22.0  # seconds lost in a pitstop

class CarState:
    def __init__(self, name, color, driver_skill=0.9, aggression=0.5):
        self.name = name
        self.color = color
        self.driver_skill = driver_skill  # 0-1
        self.aggression = aggression  # 0-1
        self.tyre = 'MEDIUM'
        self.wear = 0.0
        self.fuel = 100.0  # arbitrary units
        self.laptime = 0.0
        self.total_time = 0.0
        self.laps_completed = 0
        self.on_pit = False
        self.pit_counter = 0.0
        self.s = 0.0  # distance along track (meters)
        self.v = 0.0  # speed scalar (m/s)
        self.lap_sector = 0
        self.last_lap_time = None
        self.status = 'OK'
        self.position = None
        
        # Enhanced physics parameters
        self.engine_rpm = 5000.0  # RPM
        self.gear = 1  # Current gear (1-8)
        self.throttle = 0.0  # Throttle input (0-1)
        self.brake_pressure = 0.0  # Brake input (0-1)
        self.tire_temp = 100.0  # Tire temperature (°C)
        self.tire_pressure = 1.0  # Tire pressure (bar)
        self.aero_downforce = 0.0  # Downforce (N)
        self.drag_coeff = 0.75  # Drag coefficient
        self.yaw_rate = 0.0  # Yaw rate (rad/s)
        self.slip_angle = 0.0  # Slip angle (rad)
        self.engine_mode = 'normal'  # 'conservative', 'normal', 'aggressive'
        self.drs_active = False  # DRS active
        self.ers_energy = 100.0  # ERS energy (%)
        
        # Car parameters
        self.mass = 798.0  # kg
        self.power_max = 746000.0  # Watts
        self.brake_bias = 0.6  # Front brake bias
        self.suspension_stiffness = 50000.0  # N/m
        self.tire_compound = 'MEDIUM'  # Tire compound
        
        # Controller and behavior
        self.lidar = None  # LiDAR scan data
        self.controller_type = 'pure_pursuit'  # Current controller type
        self.overtaking = False  # Currently overtaking
        self.target_line_offset = 0.0  # Racing line offset
        
        # Track temperature (for tire temp calculation)
        self.track_temp = 25.0

    def lap_progress_fraction(self, track):
        return (self.s % track['total_length']) / track['total_length']


class RaceSim:
    def __init__(self, track_layout, n_cars=8, weather=None):
        self.track = track_layout
        self.cars = []
        self.dt = 0.5  # seconds per physics update (coarse)
        self.time = 0.0
        self.weather = weather or {'rain': 0.0, 'track_temp': 25.0, 'wind': 0.0}
        
        # Import enhanced modules
        try:
            from enhanced_physics import PhysicsEngine
            from lidar_simulator import LidarSimulator
            from controller_adapter import ControllerAdapter
            from advanced_driving import AdvancedDriving
            
            self.physics_engine = PhysicsEngine()
            self.lidar_simulator = LidarSimulator(num_rays=360, max_range=10.0, track_width=12.0)
            self.advanced_driving = AdvancedDriving()
            
            # Create controller adapters for each car (will be initialized in init_cars)
            self.controller_adapters = {}
            
            # Pre-compute track boundaries for LiDAR
            self.track_boundaries = None
            
        except ImportError as e:
            print(f"Warning: Could not import enhanced modules: {e}")
            print("Falling back to basic physics")
            self.physics_engine = None
            self.lidar_simulator = None
            self.advanced_driving = None
            self.controller_adapters = {}
            self.track_boundaries = None
        
        self.init_cars(n_cars)
        self.total_laps = 20

    def init_cars(self, n):
        colors = plt.cm.tab10.colors
        
        # Pre-compute track boundaries if LiDAR is available
        if self.lidar_simulator and self.track_boundaries is None:
            self.track_boundaries = self.lidar_simulator.generate_track_boundaries(self.track)
        
        for i in range(n):
            name = f'Driver {i+1}'
            c = CarState(name, colors[i % len(colors)],
                         driver_skill=0.75 + random.random()*0.25,
                         aggression=0.3 + random.random()*0.7)
            # spread start positions slightly
            c.s = i * (self.track['total_length'] / n) * 0.6
            c.v = 0.0
            c.tyre = random.choice(['SOFT', 'MEDIUM', 'HARD'])
            c.tire_compound = c.tyre
            c.track_temp = self.weather.get('track_temp', 25.0)
            c.tire_temp = self.weather.get('track_temp', 25.0) + 10.0  # Start slightly above ambient
            
            # Initialize controller adapter
            if self.controller_adapters is not None:
                from controller_adapter import ControllerAdapter
                self.controller_adapters[c.name] = ControllerAdapter(
                    follow_gap_params={'target_speed': 0.8, 'aggressiveness': c.aggression},
                    pure_pursuit_params={'target_speed': 0.8, 'aggressiveness': c.aggression}
                )
            
            self.cars.append(c)

    def tyre_grip_coeff(self, car):
        base = TYRE_BASE.get(car.tyre, 0.95)
        # Wear impact is compound-specific - softer compounds degrade faster with wear
        wear_impact = 0.6 if car.tyre == 'SOFT' else (0.5 if car.tyre == 'MEDIUM' else 0.4)
        grip = base * (1 - wear_impact * car.wear)
        
        # Temperature effect (optimal around 90-110°C)
        temp = getattr(car, 'tire_temp', 100.0)
        if temp < 80 or temp > 120:
            temp_factor = 1.0 - 0.2 * abs((temp - 100.0) / 100.0)
            temp_factor = max(0.7, temp_factor)
            grip *= temp_factor
        
        # rain reduces dry tyre grip greatly; wet compound has higher traction in rain
        rain = self.weather['rain']
        if car.tyre == 'WET':
            grip *= (1.0 + 0.5 * rain)
        else:
            grip *= (1.0 - 0.9 * rain)
        # driver skill modifies effective grip handling
        grip *= (0.8 + 0.4 * car.driver_skill)
        return max(grip, 0.05)

    def cornering_speed(self, car, curvature):
        # Simplified cornering speed model: v = sqrt(grip / curvature * k)
        # Add scale conversion so typical v values are realistic (m/s)
        grip = self.tyre_grip_coeff(car)
        k = 12.0  # scaling constant to tune speeds
        # Prevent division by zero
        curv = max(curvature, 1e-6)
        v = math.sqrt(grip * k / curv)
        # heavier fuel reduces top speed linearly
        v *= (1 - 0.001 * car.fuel)
        return v

    def straight_speed(self, car):
        # Simple top speed dependent on aero and tyre
        base = 80.0 + 20.0 * (car.driver_skill)  # m/s
        # Compound performance: SOFT fastest, HARD slowest
        compound_multiplier = TYRE_BASE.get(car.tyre, 0.95)
        base *= compound_multiplier
        # rain and wet tyres reduce top speed
        base *= (1 - 0.25 * self.weather['rain'])
        base *= (0.95 + 0.1 * self.tyre_grip_coeff(car))
        # fuel penalty
        base *= (1 - 0.001 * car.fuel)
        return base

    def error_probability(self, car):
        # chance per second to make an error
        rain = self.weather['rain']
        wear = car.wear
        base = 0.0005 + 0.001 * (1 - car.driver_skill)
        prob = base * (1 + 4 * rain + 6 * wear + car.aggression)
        return min(prob, 0.5)

    def step(self):
        # One physics step (self.dt seconds)
        for car in self.cars:
            if car.on_pit:
                # Handle pit stop
                car.pit_counter -= self.dt
                if car.pit_counter <= 0:
                    car.on_pit = False
                    car.pit_counter = 0
                    car.tyre = random.choice(['SOFT', 'MEDIUM', 'HARD'])
                    car.tire_compound = car.tyre
                    car.wear *= 0.15
                    car.fuel = 100.0
                continue
            
            # Get track position and curvature
            u = self.track['s_to_u'](car.s)
            curv = self.track['curv'](u)
            car.track_temp = self.weather.get('track_temp', 25.0)
            
            # Generate LiDAR scan if available
            lidar_data = None
            if self.lidar_simulator:
                try:
                    lidar_data = self.lidar_simulator.generate_lidar_for_car(
                        car, self.track, self.cars, self.track_boundaries
                    )
                    car.lidar = lidar_data
                except Exception as e:
                    # Fallback: generate dummy LiDAR
                    lidar_data = np.ones(360) * 10.0
                    car.lidar = lidar_data
            
            # Advanced driving behaviors
            car_ahead = None
            overtaking_maneuver = None
            drs_eligible = False
            
            if self.advanced_driving:
                # Detect car ahead
                car_ahead = self.advanced_driving.detect_car_ahead(
                    car, self.cars, self.track, self.track['total_length']
                )
                
                # Check DRS eligibility
                drs_eligible = self.advanced_driving.check_drs_eligibility(
                    car, car_ahead, self.track
                )
                car.drs_active = drs_eligible
                
                # Check overtaking opportunity
                if car_ahead and lidar_data is not None:
                    gap_info = self.advanced_driving.check_overtaking_gap(
                        car, car_ahead, lidar_data, self.track
                    )
                    if gap_info['can_overtake']:
                        overtaking_maneuver = self.advanced_driving.plan_overtaking_maneuver(
                            car, car_ahead, gap_info, self.track
                        )
                        car.overtaking = True
                        car.target_line_offset = overtaking_maneuver.get('target_line_offset', 0.0)
                    else:
                        car.overtaking = False
                else:
                    car.overtaking = False
            
            # Get controller action
            throttle = 0.0
            brake = 0.0
            steering = 0.0
            
            if self.controller_adapters and car.name in self.controller_adapters:
                try:
                    controller = self.controller_adapters[car.name]
                    action = controller.get_action(car, self.track, lidar_data, curv)
                    
                    # Extract throttle/brake from motor output
                    motor = action.get('motor', 0.0)
                    throttle = max(0.0, motor)
                    brake = max(0.0, -motor)
                    steering = action.get('steering', 0.0)
                    car.controller_type = action.get('controller_type', 'pure_pursuit')
                    
                    # Apply overtaking adjustments
                    if overtaking_maneuver:
                        steering += overtaking_maneuver.get('steering_adjustment', 0.0)
                        throttle_boost = overtaking_maneuver.get('throttle_boost', 0.0)
                        throttle = min(1.0, throttle + throttle_boost)
                    
                except Exception as e:
                    # Fallback to basic control
                    print(f"Controller error for {car.name}: {e}")
                    throttle, brake, steering = self._basic_control(car, curv)
            else:
                # Fallback to basic control
                throttle, brake, steering = self._basic_control(car, curv)
            
            # Apply slipstream effect
            if self.advanced_driving and car_ahead:
                slipstream_boost = self.advanced_driving.calculate_slipstream_effect(car, car_ahead)
                car.v *= slipstream_boost
            
            # Apply enhanced physics if available
            if self.physics_engine:
                try:
                    # Update tire grip based on temperature and wear
                    tire_grip = self.tyre_grip_coeff(car)
                    car.tire_grip = tire_grip
                    
                    # Apply physics step
                    new_speed = self.physics_engine.apply_physics_step(
                        car, throttle, brake, steering, self.dt, curv
                    )
                    car.v = new_speed
                except Exception as e:
                    # Fallback to basic physics
                    print(f"Physics error for {car.name}: {e}")
                    car.v = self._basic_physics(car, throttle, brake, curv)
            else:
                # Basic physics fallback
                car.v = self._basic_physics(car, throttle, brake, curv)
            
            # Store control inputs
            car.throttle = throttle
            car.brake_pressure = brake
            
            # Random incident
            if random.random() < self.error_probability(car) * self.dt:
                r = random.random()
                if r < 0.6:
                    car.v *= 0.6
                    car.total_time += 2.0
                elif r < 0.9:
                    car.v = 0.0
                    car.total_time += 6.0
                else:
                    car.on_pit = True
                    car.pit_counter = PIT_TIME
                    car.total_time += PIT_TIME
            
            # Compound-specific tyre wear
            wear_rate = TYRE_WEAR_RATES.get(car.tyre, 1.0)
            base_wear_rate = 0.0005 * (1 + 0.8 * (1 - self.tyre_grip_coeff(car)))
            car.wear += base_wear_rate * wear_rate * self.dt
            car.wear = min(car.wear, 0.99)
            
            # Update tire temperature (if not using enhanced physics, use basic model)
            if not self.physics_engine:
                ambient_temp = self.weather.get('track_temp', 25.0)
                heat_factor = TYRE_HEAT_FACTORS.get(car.tyre, 1.0)
                # Heat generation from speed and cornering
                slip_angle = abs(curv) * car.v if car.v > 0 else 0
                heat_gen = 0.01 * car.v * slip_angle * heat_factor
                # Cooling
                cooling = 0.05 * (car.tire_temp - ambient_temp)
                # Temperature change
                dtemp = (heat_gen - cooling) * self.dt
                car.tire_temp = max(ambient_temp, min(car.tire_temp + dtemp, 150.0))
            
            car.fuel -= 0.02 * self.dt * (1 + throttle * 0.5)  # More fuel at high throttle
            if car.fuel < 0:
                car.fuel = 0
            
            # Move along track
            car.s += car.v * self.dt
            
            # Lap crossing detection
            L = self.track['total_length']
            if (car.s // L) > ((car.s - car.v * self.dt) // L):
                car.laps_completed += 1

        self.time += self.dt
    
    def _basic_control(self, car, curvature):
        """Fallback basic control logic"""
        v_corner = self.cornering_speed(car, curvature)
        v_straight = self.straight_speed(car)
        target_v = min(v_straight, v_corner)
        
        if car.v < target_v:
            throttle = 0.8
            brake = 0.0
        else:
            throttle = 0.0
            brake = 0.5
        
        steering = 0.0  # Basic control doesn't steer
        
        return throttle, brake, steering
    
    def _basic_physics(self, car, throttle, brake, curvature):
        """Fallback basic physics"""
        v_corner = self.cornering_speed(car, curvature)
        v_straight = self.straight_speed(car)
        target_v = min(v_straight, v_corner)
        
        if car.v < target_v:
            car.v += 6.0 * self.dt * throttle
        else:
            car.v -= 10.0 * self.dt * brake
        
        car.v = max(0.0, min(car.v, v_straight))
        return car.v

    def get_leaderboard(self):
        # Rank by laps completed then total distance covered then total_time
        sorted_cars = sorted(self.cars, key=lambda c: (-c.laps_completed, -(c.s % self.track['total_length']), c.total_time))
        for i, c in enumerate(sorted_cars):
            c.position = i + 1
        return sorted_cars

# -------------------- Visualization & Dashboard --------------------

def make_dashboard(sim, figsize=(18,10)):
    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(2, 3)

    ax_track = fig.add_subplot(gs[:, 0:2])  # big track view
    ax_leader = fig.add_subplot(gs[0, 2])   # leaderboard
    ax_info = fig.add_subplot(gs[1, 2])     # telemetry / weather

    ax_track.set_title('2D F1 Simulator — Track View')
    ax_track.set_aspect('equal')
    ax_track.axis('off')

    ax_leader.set_title('Live Leaderboard')
    ax_leader.axis('off')

    ax_info.set_title('Race Info')
    ax_info.axis('off')

    return fig, ax_track, ax_leader, ax_info


def draw_static_track(ax, track):
    # draw track centerline and approximate boundaries
    ss = track['ss']
    pts = track['pos'](ss)
    ax.plot(pts[:, 0], pts[:, 1], linewidth=3, color='black')
    # draw a faint polygon offset to represent track limits
    ax.plot(pts[:, 0], pts[:, 1], linewidth=1, color='grey', alpha=0.3)


def update_frame(frame, sim, artists):
    fig, ax_track, ax_leader, ax_info = artists['fig_axes']

    # advance sim several steps per animation frame for speed
    steps_per_frame = 6
    for _ in range(steps_per_frame):
        sim.step()

    # redraw track and cars
    ax_track.clear(); ax_track.set_aspect('equal'); ax_track.axis('off')
    draw_static_track(ax_track, sim.track)

    # draw cars as triangles at spline positions
    for car in sim.cars:
        u = sim.track['s_to_u'](car.s)
        x, y = sim.track['pos'](u)[0]
        # heading approx via small forward offset
        u2 = sim.track['s_to_u'](car.s + 1.0)
        x2, y2 = sim.track['pos'](u2)[0]
        angle = math.atan2(y2 - y, x2 - x)
        # triangle marker
        tri = patches.RegularPolygon((x, y), numVertices=3, radius=10 + 6*(1-car.wear), orientation=angle, color=car.color)
        ax_track.add_patch(tri)
        ax_track.text(x+12, y+12, f"{car.position or '?'} {car.name}", fontsize=9, color='black')

    # Leaderboard: big text table
    ax_leader.clear(); ax_leader.axis('off')
    lb = sim.get_leaderboard()
    # Create large formatted table on ax_leader
    y = 0.95
    ax_leader.text(0.02, y, f"TIME: {sim.time:0.1f}s", fontsize=14, weight='bold')
    y -= 0.08
    ax_leader.text(0.02, y, "Pos  Driver        Laps  Wear  Tyre   Fuel", fontsize=12, weight='bold')
    y -= 0.06
    for c in lb:
        s = f"{c.position:>2}   {c.name:<12}  {c.laps_completed:>3}   {c.wear:0.2f}  {c.tyre:<6}  {c.fuel:0.0f}"
        ax_leader.text(0.02, y, s, fontsize=12)
        y -= 0.05

    # Info box
    ax_info.clear(); ax_info.axis('off')
    w = sim.weather
    ax_info.text(0.02, 0.9, f"Weather: Rain {w['rain']:.2f}  TrackT {w['track_temp']:.1f}C", fontsize=12)
    ax_info.text(0.02, 0.8, f"Total Laps Target: {sim.total_laps}", fontsize=12)
    ax_info.text(0.02, 0.7, f"Cars: {len(sim.cars)}", fontsize=12)

    # small hist of tyre distribution
    tyre_counts = {}
    for c in sim.cars:
        tyre_counts[c.tyre] = tyre_counts.get(c.tyre, 0) + 1
    txt = '\n'.join([f"{k}: {v}" for k, v in tyre_counts.items()])
    ax_info.text(0.02, 0.45, "Tyre distro:\n" + txt, fontsize=11)

    return []

# -------------------- Put it all together --------------------

def run_colab_simulation():
    waypoints = load_gp_track('Silverstone')
    track = build_spline(waypoints, n_points=2000)

    # initial weather example
    weather = {'rain': 0.15, 'track_temp': 22.0, 'wind': 3.0}

    sim = RaceSim(track, n_cars=10, weather=weather)
    sim.total_laps = 12

    fig, ax_track, ax_leader, ax_info = make_dashboard(sim, figsize=(20,12))
    artists = {'fig_axes': (fig, ax_track, ax_leader, ax_info)}

    ani = FuncAnimation(fig, update_frame, fargs=(sim, artists), interval=200)
    plt.show()

# If run as script or in a Jupyter cell, call run_colab_simulation()
if __name__ == '__main__':
    run_colab_simulation()
