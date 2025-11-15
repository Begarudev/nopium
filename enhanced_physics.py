"""
Enhanced Physics Engine for 2D F1 Simulator
Implements realistic F1 car physics including:
- Power-limited acceleration with gear ratios
- Speed-dependent braking with ABS
- Aerodynamic forces (drag and downforce)
- Tire model (simplified Pacejka)
- Weight transfer
- Suspension model
"""

import numpy as np
import math


class PhysicsEngine:
    """Enhanced physics engine for F1 car simulation"""
    
    # F1 Car Constants
    MASS = 798.0  # kg (F1 car + driver + fuel)
    POWER_MAX = 746000.0  # Watts (~1000 HP)
    DRAG_COEFF = 0.75  # Cd
    DOWNFORCE_COEFF = 3.5  # Cl
    FRONTAL_AREA = 1.5  # m^2
    AIR_DENSITY = 1.225  # kg/m^3 at sea level
    GRAVITY = 9.81  # m/s^2
    
    # Gear ratios (8-speed transmission)
    GEAR_RATIOS = [2.9, 2.0, 1.5, 1.2, 1.0, 0.85, 0.75, 0.65]
    FINAL_DRIVE = 3.5
    WHEEL_RADIUS = 0.33  # m
    
    # Braking
    BRAKE_BIAS_FRONT = 0.6  # 60% front, 40% rear
    MAX_BRAKE_DECEL = 5.0 * GRAVITY  # 5g max deceleration
    BRAKE_FRICTION = 1.2
    
    # Tire model (simplified Pacejka)
    TIRE_B = 10.0  # Stiffness factor
    TIRE_C = 1.9   # Shape factor
    TIRE_D = 1.0   # Peak value
    
    # Suspension
    SUSPENSION_STIFFNESS = 50000.0  # N/m
    SUSPENSION_DAMPING = 5000.0     # Ns/m
    
    def __init__(self):
        self.max_rpm = 15000
        self.idle_rpm = 5000
        
    def calculate_engine_power(self, rpm, engine_mode='normal'):
        """
        Calculate engine power at given RPM.
        Power curve peaks around 12,000 RPM.
        """
        # Normalize RPM
        rpm_norm = np.clip(rpm / self.max_rpm, 0, 1)
        
        # Power curve: peak at ~0.8 (12k RPM)
        power_factor = np.sin(rpm_norm * np.pi * 0.625)  # Peak at 0.8
        
        # Engine mode multipliers
        mode_multipliers = {
            'conservative': 0.85,
            'normal': 1.0,
            'aggressive': 1.15
        }
        multiplier = mode_multipliers.get(engine_mode, 1.0)
        
        return self.POWER_MAX * power_factor * multiplier
    
    def calculate_rpm_from_speed(self, speed, gear):
        """
        Calculate engine RPM from vehicle speed and gear.
        """
        if gear < 1 or gear > len(self.GEAR_RATIOS):
            return self.idle_rpm
        
        # Effective gear ratio
        gear_ratio = self.GEAR_RATIOS[gear - 1] * self.FINAL_DRIVE
        
        # RPM = (speed / wheel_radius) * gear_ratio * (60 / (2 * pi))
        rpm = (speed / self.WHEEL_RADIUS) * gear_ratio * 9.55
        
        return np.clip(rpm, self.idle_rpm, self.max_rpm)
    
    def select_gear(self, speed, current_gear, throttle):
        """
        Simple gear selection logic based on speed and RPM.
        """
        if speed < 5.0:  # Very slow, use first gear
            return 1
        
        # Calculate RPM for current gear
        rpm = self.calculate_rpm_from_speed(speed, current_gear)
        
        # Upshift if RPM too high
        if rpm > 14000 and current_gear < len(self.GEAR_RATIOS):
            return current_gear + 1
        
        # Downshift if RPM too low and throttle applied
        if rpm < 8000 and current_gear > 1 and throttle > 0.5:
            return current_gear - 1
        
        return current_gear
    
    def calculate_acceleration(self, speed, throttle, gear, engine_mode='normal', mass=None):
        """
        Calculate acceleration using power-limited model.
        Formula: a = (P / (m * v)) - drag_force/m
        """
        if mass is None:
            mass = self.MASS
        
        if speed < 0.1:  # Prevent division by zero
            speed = 0.1
        
        # Calculate RPM and power
        rpm = self.calculate_rpm_from_speed(speed, gear)
        power = self.calculate_engine_power(rpm, engine_mode) * throttle
        
        # Power-limited acceleration
        # P = F * v, so F = P / v, and a = F / m
        power_accel = power / (mass * speed)
        
        # Aerodynamic drag
        drag_force = 0.5 * self.AIR_DENSITY * self.DRAG_COEFF * self.FRONTAL_AREA * speed ** 2
        
        # Rolling resistance (simplified)
        rolling_resistance = 0.02 * mass * self.GRAVITY
        
        # Net acceleration
        net_force = (power / speed) - drag_force - rolling_resistance
        acceleration = net_force / mass
        
        # Limit acceleration (traction limited)
        max_accel = 2.0 * self.GRAVITY  # ~2g max acceleration
        acceleration = np.clip(acceleration, 0, max_accel)
        
        return acceleration, rpm
    
    def calculate_braking(self, speed, brake_pressure, mass=None):
        """
        Calculate deceleration using speed-dependent braking model.
        Formula: brake_force = brake_pressure * friction_coeff * (1 - v/v_max)^0.5
        """
        if mass is None:
            mass = self.MASS
        
        if speed < 0.1:
            return 0.0
        
        # Speed-dependent brake effectiveness
        v_max = 100.0  # m/s (~360 km/h)
        speed_factor = (1 - speed / v_max) ** 0.5
        
        # Brake force (front and rear)
        brake_force_total = brake_pressure * self.BRAKE_FRICTION * speed_factor * mass * self.GRAVITY
        
        # Weight transfer during braking (more load on front)
        weight_transfer = 0.1 * brake_force_total / mass  # Simplified
        
        # Front/rear brake distribution
        front_load = mass * self.GRAVITY * 0.5 + weight_transfer
        rear_load = mass * self.GRAVITY * 0.5 - weight_transfer
        
        front_brake = brake_force_total * self.BRAKE_BIAS_FRONT * (front_load / (mass * self.GRAVITY))
        rear_brake = brake_force_total * (1 - self.BRAKE_BIAS_FRONT) * (rear_load / (mass * self.GRAVITY))
        
        total_brake_force = front_brake + rear_brake
        
        # Deceleration
        deceleration = total_brake_force / mass
        
        # ABS-like behavior: limit deceleration
        deceleration = np.clip(deceleration, 0, self.MAX_BRAKE_DECEL)
        
        return deceleration
    
    def calculate_aerodynamic_forces(self, speed, drs_active=False):
        """
        Calculate aerodynamic drag and downforce.
        Drag: F_drag = 0.5 * rho * Cd * A * v^2
        Downforce: F_down = 0.5 * rho * Cl * A * v^2
        """
        drag_coeff = self.DRAG_COEFF
        if drs_active:
            drag_coeff *= 0.85  # 15% drag reduction with DRS
        
        drag_force = 0.5 * self.AIR_DENSITY * drag_coeff * self.FRONTAL_AREA * speed ** 2
        downforce = 0.5 * self.AIR_DENSITY * self.DOWNFORCE_COEFF * self.FRONTAL_AREA * speed ** 2
        
        return drag_force, downforce
    
    def calculate_tire_forces(self, slip_angle, normal_load, tire_temp=100.0, tire_compound='MEDIUM'):
        """
        Simplified Pacejka tire model for lateral forces.
        F_y = D * sin(C * arctan(B * slip_angle))
        
        Args:
            slip_angle: Tire slip angle in radians
            normal_load: Normal load on tire (N)
            tire_temp: Tire temperature (°C)
            tire_compound: Tire compound ('SOFT', 'MEDIUM', 'HARD', 'WET')
        """
        # Compound multipliers
        compound_multipliers = {
            'SOFT': 1.0,
            'MEDIUM': 0.95,
            'HARD': 0.90,
            'WET': 0.78
        }
        compound_factor = compound_multipliers.get(tire_compound, 0.95)
        
        # Temperature effect (optimal around 100°C)
        temp_factor = 1.0 - 0.3 * abs((tire_temp - 100.0) / 100.0)
        temp_factor = np.clip(temp_factor, 0.7, 1.0)
        
        # Load sensitivity
        load_factor = np.sqrt(normal_load / (self.MASS * self.GRAVITY / 4))  # Per tire
        
        # Pacejka model
        B = self.TIRE_B * compound_factor * temp_factor
        C = self.TIRE_C
        D = self.TIRE_D * normal_load * load_factor * compound_factor * temp_factor
        
        # Lateral force
        lateral_force = D * np.sin(C * np.arctan(B * slip_angle))
        
        return lateral_force
    
    def calculate_weight_transfer(self, acceleration, deceleration, lateral_accel):
        """
        Calculate weight transfer during acceleration, braking, and cornering.
        Returns front/rear and left/right load distribution.
        """
        # Longitudinal weight transfer
        long_transfer = (acceleration - deceleration) * self.MASS * 0.3 / self.MASS  # Simplified
        
        # Lateral weight transfer
        lat_transfer = lateral_accel * self.MASS * 0.4 / self.MASS  # Simplified
        
        # Base loads (equal distribution)
        front_load = self.MASS * self.GRAVITY * 0.5 - long_transfer
        rear_load = self.MASS * self.GRAVITY * 0.5 + long_transfer
        
        left_load = self.MASS * self.GRAVITY * 0.5 - lat_transfer
        right_load = self.MASS * self.GRAVITY * 0.5 + lat_transfer
        
        return {
            'front': front_load,
            'rear': rear_load,
            'left': left_load,
            'right': right_load
        }
    
    def calculate_suspension_force(self, displacement, velocity):
        """
        Simple spring-damper suspension model.
        """
        spring_force = -self.SUSPENSION_STIFFNESS * displacement
        damper_force = -self.SUSPENSION_DAMPING * velocity
        
        return spring_force + damper_force
    
    def update_tire_temperature(self, current_temp, speed, slip_angle, normal_load, ambient_temp=25.0, dt=0.1, tire_compound='MEDIUM'):
        """
        Update tire temperature based on usage.
        """
        # Compound-specific heat factors
        compound_heat_factors = {
            'SOFT': 1.2,
            'MEDIUM': 1.0,
            'HARD': 0.8,
            'WET': 0.9
        }
        heat_factor = compound_heat_factors.get(tire_compound, 1.0)
        
        # Heat generation from friction
        heat_gen = 0.01 * speed * abs(slip_angle) * (normal_load / (self.MASS * self.GRAVITY / 4)) * heat_factor
        
        # Cooling (convection)
        cooling = 0.05 * (current_temp - ambient_temp)
        
        # Temperature change
        dtemp = (heat_gen - cooling) * dt
        
        new_temp = current_temp + dtemp
        
        # Clamp to reasonable range
        new_temp = np.clip(new_temp, ambient_temp, 150.0)
        
        return new_temp
    
    def calculate_cornering_speed(self, curvature, downforce, tire_grip):
        """
        Calculate maximum cornering speed based on curvature and available grip.
        v = sqrt((grip * g * radius) / (1 + downforce_factor))
        """
        if curvature < 1e-6:
            return 1000.0  # Straight
        
        radius = 1.0 / curvature
        
        # Effective grip with downforce
        downforce_factor = downforce / (self.MASS * self.GRAVITY)
        effective_grip = tire_grip * (1 + 0.3 * downforce_factor)  # Downforce increases grip
        
        # Maximum cornering speed
        v_max = np.sqrt(effective_grip * self.GRAVITY * radius)
        
        return v_max
    
    def apply_physics_step(self, car_state, throttle, brake, steering, dt, track_curvature=0.0):
        """
        Apply physics step to car state.
        
        Args:
            car_state: CarState object with physics parameters
            throttle: Throttle input (0-1)
            brake: Brake input (0-1)
            steering: Steering input (-1 to 1)
            dt: Time step
            track_curvature: Track curvature at current position
        
        Returns:
            Updated velocity and other physics parameters
        """
        # Get current state
        speed = car_state.v
        gear = getattr(car_state, 'gear', 5)
        engine_mode = getattr(car_state, 'engine_mode', 'normal')
        drs_active = getattr(car_state, 'drs_active', False)
        tire_temp = getattr(car_state, 'tire_temp', 100.0)
        tire_compound = getattr(car_state, 'tyre', 'MEDIUM')
        mass = self.MASS + car_state.fuel * 0.7  # Fuel adds mass (~0.7 kg per unit)
        
        # Update gear
        gear = self.select_gear(speed, gear, throttle)
        car_state.gear = gear
        
        # Calculate acceleration
        if throttle > 0.01:
            accel, rpm = self.calculate_acceleration(speed, throttle, gear, engine_mode, mass)
            car_state.engine_rpm = rpm
        else:
            accel = 0.0
            car_state.engine_rpm = self.idle_rpm
        
        # Calculate braking
        if brake > 0.01:
            decel = self.calculate_braking(speed, brake, mass)
        else:
            decel = 0.0
        
        # Aerodynamic forces
        drag_force, downforce = self.calculate_aerodynamic_forces(speed, drs_active)
        car_state.aero_downforce = downforce
        
        # Calculate slip angle (simplified)
        if speed > 0.1:
            slip_angle = np.arctan(steering * 0.1)  # Simplified
        else:
            slip_angle = 0.0
        
        # Weight transfer
        lateral_accel = speed ** 2 * track_curvature if speed > 0.1 else 0.0
        weight_transfer = self.calculate_weight_transfer(accel, decel, lateral_accel)
        
        # Tire forces
        normal_load = weight_transfer['front'] / 2  # Per front tire
        tire_force = self.calculate_tire_forces(slip_angle, normal_load, tire_temp, tire_compound)
        
        # Update tire temperature
        tire_compound = getattr(car_state, 'tire_compound', getattr(car_state, 'tyre', 'MEDIUM'))
        tire_temp = self.update_tire_temperature(
            tire_temp, speed, slip_angle, normal_load,
            ambient_temp=getattr(car_state, 'track_temp', 25.0),
            dt=dt,
            tire_compound=tire_compound
        )
        car_state.tire_temp = tire_temp
        
        # Net acceleration
        net_accel = accel - decel - (drag_force / mass)
        
        # Update velocity
        new_speed = speed + net_accel * dt
        new_speed = max(0.0, new_speed)
        
        # Calculate maximum cornering speed
        tire_grip = getattr(car_state, 'tire_grip', 1.0)
        max_corner_speed = self.calculate_cornering_speed(track_curvature, downforce, tire_grip)
        
        # Limit speed by cornering capability
        if track_curvature > 1e-6:
            new_speed = min(new_speed, max_corner_speed)
        
        return new_speed

