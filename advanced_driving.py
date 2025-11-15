"""
Advanced Driving Behaviors for F1 Simulator
Implements overtaking logic, racing line optimization, DRS, and slipstream effects.
"""

import numpy as np
import math


class AdvancedDriving:
    """Advanced driving behaviors for F1 racing"""
    
    def __init__(self):
        # Overtaking parameters
        self.overtaking_distance_threshold = 2.0  # seconds behind car ahead
        self.overtaking_gap_threshold = 1.5  # meters minimum gap
        self.overtaking_lookahead = 5.0  # meters ahead to check
        
        # DRS parameters
        self.drs_activation_distance = 1.0  # seconds behind car ahead
        self.drs_drag_reduction = 0.15  # 15% drag reduction
        self.drs_min_speed = 50.0  # km/h minimum speed for DRS
        
        # Slipstream parameters
        self.slipstream_distance = 0.5  # seconds behind
        self.slipstream_boost_max = 0.05  # 5% speed boost
        self.slipstream_range = 2.0  # meters
        
        # Racing line parameters
        self.racing_line_lookahead = 3.0  # seconds ahead
    
    def detect_car_ahead(self, car, all_cars, track_spline, track_length):
        """
        Detect if there's a car ahead within threshold distance.
        
        Args:
            car: Current car
            all_cars: List of all cars
            track_spline: Track spline dict
            track_length: Total track length
        
        Returns:
            Car ahead dict with 'car', 'distance', 'time_gap', or None
        """
        car_ahead = None
        min_distance = float('inf')
        min_time_gap = float('inf')
        
        for other in all_cars:
            if other is car or other.on_pit:
                continue
            
            # Calculate distance along track
            distance_along_track = (other.s - car.s) % track_length
            
            # If distance is very small, car might be behind
            if distance_along_track < 0.1:
                distance_along_track = track_length - distance_along_track
            
            # Check if car is ahead
            if 0.1 < distance_along_track < track_length / 2:
                # Calculate time gap
                if car.v > 0.1:
                    time_gap = distance_along_track / car.v
                else:
                    time_gap = float('inf')
                
                # Check if within threshold
                if time_gap < self.overtaking_distance_threshold:
                    if time_gap < min_time_gap:
                        min_time_gap = time_gap
                        min_distance = distance_along_track
                        car_ahead = other
        
        if car_ahead:
            return {
                'car': car_ahead,
                'distance': min_distance,
                'time_gap': min_time_gap
            }
        
        return None
    
    def check_overtaking_gap(self, car, car_ahead, lidar_data, track_spline):
        """
        Check if there's a gap suitable for overtaking.
        
        Args:
            car: Current car
            car_ahead: Car ahead dict
            lidar_data: LiDAR scan
            track_spline: Track spline dict
        
        Returns:
            Dict with 'can_overtake', 'side' ('left' or 'right'), 'gap_size'
        """
        if len(lidar_data) == 0:
            return {'can_overtake': False}
        
        # Focus on front-left and front-right sectors
        n_rays = len(lidar_data)
        front_start = n_rays // 4
        front_end = 3 * n_rays // 4
        front_lidar = lidar_data[front_start:front_end]
        
        # Split into left and right
        mid = len(front_lidar) // 2
        left_lidar = front_lidar[:mid]
        right_lidar = front_lidar[mid:]
        
        # Find gaps in each side
        def find_largest_gap(sector_lidar):
            gaps = []
            in_gap = False
            gap_start = None
            
            for i, dist in enumerate(sector_lidar):
                if dist > self.overtaking_gap_threshold:
                    if not in_gap:
                        gap_start = i
                        in_gap = True
                else:
                    if in_gap:
                        gap_size = i - gap_start
                        gaps.append({'start': gap_start, 'end': i, 'size': gap_size})
                        in_gap = False
            
            if in_gap:
                gap_size = len(sector_lidar) - gap_start
                gaps.append({'start': gap_start, 'end': len(sector_lidar), 'size': gap_size})
            
            if gaps:
                return max(gaps, key=lambda g: g['size'])
            return None
        
        left_gap = find_largest_gap(left_lidar)
        right_gap = find_largest_gap(right_lidar)
        
        # Determine which side has better gap
        if left_gap and right_gap:
            if left_gap['size'] > right_gap['size']:
                return {
                    'can_overtake': True,
                    'side': 'left',
                    'gap_size': left_gap['size'],
                    'gap_center': (left_gap['start'] + left_gap['end']) // 2
                }
            else:
                return {
                    'can_overtake': True,
                    'side': 'right',
                    'gap_size': right_gap['size'],
                    'gap_center': (right_gap['start'] + right_gap['end']) // 2
                }
        elif left_gap:
            return {
                'can_overtake': True,
                'side': 'left',
                'gap_size': left_gap['size'],
                'gap_center': (left_gap['start'] + left_gap['end']) // 2
            }
        elif right_gap:
            return {
                'can_overtake': True,
                'side': 'right',
                'gap_size': right_gap['size'],
                'gap_center': (right_gap['start'] + right_gap['end']) // 2
            }
        
        return {'can_overtake': False}
    
    def plan_overtaking_maneuver(self, car, car_ahead, gap_info, track_spline):
        """
        Plan overtaking maneuver.
        
        Args:
            car: Current car
            car_ahead: Car ahead dict
            gap_info: Gap info from check_overtaking_gap
            track_spline: Track spline dict
        
        Returns:
            Dict with 'steering_adjustment', 'throttle_boost', 'target_line_offset'
        """
        if not gap_info['can_overtake']:
            return {'steering_adjustment': 0.0, 'throttle_boost': 0.0, 'target_line_offset': 0.0}
        
        # Calculate steering adjustment based on gap side
        side = gap_info['side']
        gap_center = gap_info.get('gap_center', 0)
        
        # Normalize gap center to steering angle
        n_rays = 360  # Assume 360 rays
        front_start = n_rays // 4
        front_end = 3 * n_rays // 4
        front_size = front_end - front_start
        
        # Convert gap center to angle
        normalized_pos = (gap_center - front_size / 2) / (front_size / 2)
        steering_adjustment = np.clip(normalized_pos * 0.5, -1.0, 1.0)
        
        # Throttle boost when in slipstream
        time_gap = car_ahead['time_gap']
        if time_gap < self.slipstream_distance:
            throttle_boost = self.slipstream_boost_max * (1 - time_gap / self.slipstream_distance)
        else:
            throttle_boost = 0.0
        
        # Target line offset (move to inside/outside)
        if side == 'left':
            target_line_offset = -2.0  # Move left (inside)
        else:
            target_line_offset = 2.0  # Move right (outside)
        
        return {
            'steering_adjustment': steering_adjustment,
            'throttle_boost': throttle_boost,
            'target_line_offset': target_line_offset,
            'overtaking': True
        }
    
    def check_drs_eligibility(self, car, car_ahead, track_spline):
        """
        Check if DRS can be activated.
        
        Args:
            car: Current car
            car_ahead: Car ahead dict or None
            track_spline: Track spline dict
        
        Returns:
            True if DRS can be activated
        """
        if car.v < self.drs_min_speed / 3.6:  # Convert km/h to m/s
            return False
        
        if car_ahead is None:
            return False
        
        # Check if within activation distance
        time_gap = car_ahead['time_gap']
        if time_gap > self.drs_activation_distance:
            return False
        
        # Check if on straight (low curvature)
        u = track_spline['s_to_u'](car.s)
        curvature = track_spline['curv'](u)
        
        if abs(curvature) > 0.005:  # Not a straight
            return False
        
        return True
    
    def calculate_slipstream_effect(self, car, car_ahead):
        """
        Calculate slipstream speed boost.
        
        Args:
            car: Current car
            car_ahead: Car ahead dict or None
        
        Returns:
            Speed boost multiplier
        """
        if car_ahead is None:
            return 1.0
        
        time_gap = car_ahead['time_gap']
        
        if time_gap > self.slipstream_distance:
            return 1.0
        
        # Calculate boost based on distance
        boost_factor = 1.0 + self.slipstream_boost_max * (1 - time_gap / self.slipstream_distance)
        
        return boost_factor
    
    def calculate_racing_line(self, car, track_spline, lookahead_time=3.0):
        """
        Calculate optimal racing line waypoints.
        
        Args:
            car: Current car
            track_spline: Track spline dict
            lookahead_time: Time ahead to calculate line
        
        Returns:
            List of waypoints along racing line
        """
        waypoints = []
        lookahead_distance = car.v * lookahead_time
        
        # Sample points along track
        n_samples = 10
        for i in range(n_samples):
            s_ahead = car.s + lookahead_distance * (i + 1) / n_samples
            u_ahead = track_spline['s_to_u'](s_ahead)
            
            # Get centerline position
            pos_center = track_spline['pos'](u_ahead)[0]
            
            # Get curvature
            curvature = track_spline['curv'](u_ahead)
            
            # Calculate optimal offset
            offset = self._calculate_line_offset(curvature, car.v)
            
            # Apply offset perpendicular to track direction
            u2 = track_spline['s_to_u'](s_ahead + 1.0)
            pos2 = track_spline['pos'](u2)[0]
            dx = pos2[0] - pos_center[0]
            dy = pos2[1] - pos_center[1]
            length = np.sqrt(dx**2 + dy**2)
            
            if length > 1e-6:
                perp_x = -dy / length
                perp_y = dx / length
                
                waypoint_x = pos_center[0] + perp_x * offset
                waypoint_y = pos_center[1] + perp_y * offset
            else:
                waypoint_x = pos_center[0]
                waypoint_y = pos_center[1]
            
            waypoints.append([waypoint_x, waypoint_y])
        
        return waypoints
    
    def _calculate_line_offset(self, curvature, speed):
        """
        Calculate racing line offset from centerline.
        
        Args:
            curvature: Track curvature
            speed: Current speed
        
        Returns:
            Offset in meters (positive = outside, negative = inside)
        """
        if abs(curvature) < 1e-6:
            return 0.0  # Straight: use centerline
        
        radius = 1.0 / abs(curvature)
        
        # Racing line strategy:
        # - Slow corners (< 30 m/s): Late apex (start wide, cut inside)
        # - Medium corners (30-60 m/s): Slight inside
        # - Fast corners (> 60 m/s): Slight outside
        
        if speed < 30:
            # Late apex: wide entry, tight exit
            return -radius * 0.25  # Inside
        elif speed < 60:
            # Medium: slight inside
            return -radius * 0.15
        else:
            # Fast: slight outside for stability
            return radius * 0.1
    
    def defensive_blocking(self, car, car_behind, track_spline):
        """
        Calculate defensive blocking maneuver.
        
        Args:
            car: Current car (being overtaken)
            car_behind: Car behind dict
            track_spline: Track spline dict
        
        Returns:
            Dict with 'steering_adjustment' to block
        """
        if car_behind is None:
            return {'steering_adjustment': 0.0, 'blocking': False}
        
        # Simple blocking: move toward the side the following car is on
        # This is simplified - real F1 drivers use more sophisticated tactics
        
        # Get relative positions
        u_car = track_spline['s_to_u'](car.s)
        pos_car = track_spline['pos'](u_car)[0]
        
        u_behind = track_spline['s_to_u'](car_behind.s)
        pos_behind = track_spline['pos'](u_behind)[0]
        
        # Calculate relative angle
        dx = pos_behind[0] - pos_car[0]
        dy = pos_behind[1] - pos_car[1]
        angle = np.arctan2(dy, dx)
        
        # Get car heading
        u2 = track_spline['s_to_u'](car.s + 1.0)
        pos2 = track_spline['pos'](u2)[0]
        car_heading = np.arctan2(pos2[1] - pos_car[1], pos2[0] - pos_car[0])
        
        # Relative angle
        rel_angle = angle - car_heading
        
        # Normalize to [-pi, pi]
        while rel_angle > np.pi:
            rel_angle -= 2 * np.pi
        while rel_angle < -np.pi:
            rel_angle += 2 * np.pi
        
        # Block by moving toward the following car's side
        # But limit to reasonable amount (one move per lap rule)
        blocking_strength = 0.3  # Moderate blocking
        steering_adjustment = np.clip(rel_angle / np.pi * blocking_strength, -0.5, 0.5)
        
        return {
            'steering_adjustment': steering_adjustment,
            'blocking': True
        }
    
    def calculate_pit_strategy(self, car, race_laps_remaining, weather):
        """
        Calculate optimal pit stop strategy.
        
        Args:
            car: Current car
            race_laps_remaining: Laps remaining in race
            weather: Weather dict
        
        Returns:
            Dict with 'should_pit', 'recommended_tyre'
        """
        # Simple strategy: pit when tire wear > 70% or fuel < 20%
        should_pit = False
        recommended_tyre = car.tyre
        
        # Check tire wear
        if car.wear > 0.7:
            should_pit = True
            # Recommend softer compound if race is ending soon
            if race_laps_remaining < 5:
                recommended_tyre = 'SOFT'
            elif race_laps_remaining < 10:
                recommended_tyre = 'MEDIUM'
            else:
                recommended_tyre = 'HARD'
        
        # Check fuel
        if car.fuel < 20.0:
            should_pit = True
        
        # Check weather (switch to wet tires if rain)
        if weather.get('rain', 0) > 0.3 and car.tyre != 'WET':
            should_pit = True
            recommended_tyre = 'WET'
        
        return {
            'should_pit': should_pit,
            'recommended_tyre': recommended_tyre
        }

