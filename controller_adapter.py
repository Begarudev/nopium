"""
Controller Adapter for 2D F1 Simulator
Adapts 3D controllers to 2D coordinate system and implements hybrid controller logic.
"""

import numpy as np
import sys
import os

# Add parent directory to path to import controllers
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from racecar_gym.controllers.follow_gap import FollowGapController
    from racecar_gym.controllers.pure_pursuit import PurePursuitController
except ImportError:
    # Fallback: define simplified versions if import fails
    print("Warning: Could not import controllers from racecar_gym. Using simplified versions.")
    
    class FollowGapController:
        def __init__(self, **kwargs):
            self.target_speed = kwargs.get('target_speed', 0.8)
            self.min_gap_size = kwargs.get('min_gap_size', 0.3)
        
        def act(self, observation):
            lidar = observation.get('lidar', np.array([]))
            if len(lidar) == 0:
                return {'motor': 0.0, 'steering': 0.0}
            
            # Simple gap finding
            front_lidar = lidar[len(lidar)//4:3*len(lidar)//4]
            min_dist = np.min(front_lidar)
            
            if min_dist > 0.5:
                return {'motor': self.target_speed, 'steering': 0.0}
            else:
                # Turn toward largest gap
                left = np.mean(front_lidar[:len(front_lidar)//2])
                right = np.mean(front_lidar[len(front_lidar)//2:])
                steering = 0.5 if left > right else -0.5
                return {'motor': self.target_speed * 0.5, 'steering': steering}
    
    class PurePursuitController:
        def __init__(self, **kwargs):
            self.lookahead = kwargs.get('lookahead_distance', 0.6)
            self.target_speed = kwargs.get('target_speed', 0.8)
        
        def act(self, observation, state=None):
            return {'motor': self.target_speed, 'steering': 0.0}


class ControllerAdapter:
    """
    Adapter to use 3D controllers in 2D simulation.
    Converts 2D car state to 3D observation format and implements hybrid controller logic.
    """
    
    def __init__(self, follow_gap_params=None, pure_pursuit_params=None):
        """
        Initialize controller adapter.
        
        Args:
            follow_gap_params: Dict of parameters for FollowGapController
            pure_pursuit_params: Dict of parameters for PurePursuitController
        """
        follow_gap_params = follow_gap_params or {}
        pure_pursuit_params = pure_pursuit_params or {}
        
        self.follow_gap = FollowGapController(**follow_gap_params)
        self.pure_pursuit = PurePursuitController(**pure_pursuit_params)
        
        # Hybrid controller parameters
        self.obstacle_threshold = 3.0  # meters - switch to FollowGap if obstacle closer
        self.curvature_threshold = 0.01  # High curvature -> use PurePursuit
        self.gap_size_threshold = 0.5  # meters - large gap -> use FollowGap
        
        self.current_controller_type = 'pure_pursuit'
    
    def car_to_observation(self, car, track_spline, lidar_data=None):
        """
        Convert CarState to observation dict for controllers.
        
        Args:
            car: CarState object
            track_spline: Track spline dict
            lidar_data: LiDAR scan array (optional)
        
        Returns:
            Observation dict with 'lidar', 'pose', 'velocity'
        """
        # Get car position
        u = track_spline['s_to_u'](car.s)
        pos = track_spline['pos'](u)[0]
        x, y = pos[0], pos[1]
        
        # Calculate heading
        u2 = track_spline['s_to_u'](car.s + 1.0)
        pos2 = track_spline['pos'](u2)[0]
        yaw = np.arctan2(pos2[1] - pos[1], pos2[0] - pos[0])
        
        # Convert to 3D pose format: [x, y, z, roll, pitch, yaw]
        pose = np.array([x, y, 0.0, 0.0, 0.0, yaw])
        
        # Velocity: [vx, vy, vz]
        vx = car.v * np.cos(yaw)
        vy = car.v * np.sin(yaw)
        velocity = np.array([vx, vy, 0.0])
        
        # LiDAR data
        if lidar_data is None:
            # Generate dummy LiDAR if not provided
            lidar_data = np.ones(360) * 10.0
        
        observation = {
            'lidar': lidar_data,
            'pose': pose,
            'velocity': velocity
        }
        
        return observation
    
    def generate_waypoint(self, car, track_spline, lookahead_distance=None):
        """
        Generate waypoint for PurePursuit controller.
        
        Args:
            car: CarState object
            track_spline: Track spline dict
            lookahead_distance: Lookahead distance in meters
        
        Returns:
            Waypoint dict with 'next_waypoint' array
        """
        if lookahead_distance is None:
            lookahead_distance = self.pure_pursuit.lookahead
        
        # Calculate lookahead based on speed
        speed_factor = max(1.0, car.v / 20.0)  # Scale with speed
        adaptive_lookahead = lookahead_distance * speed_factor
        
        # Get position ahead along track
        s_ahead = car.s + adaptive_lookahead
        u_ahead = track_spline['s_to_u'](s_ahead)
        pos_ahead = track_spline['pos'](u_ahead)[0]
        
        # Convert to 3D waypoint
        waypoint = np.array([pos_ahead[0], pos_ahead[1], 0.0])
        
        return {'next_waypoint': waypoint}
    
    def should_use_follow_gap(self, lidar_data, track_curvature):
        """
        Determine if FollowGap controller should be used.
        
        Args:
            lidar_data: LiDAR scan array
            track_curvature: Current track curvature
        
        Returns:
            True if FollowGap should be used, False for PurePursuit
        """
        if len(lidar_data) == 0:
            return False
        
        # Check front sector for obstacles
        front_start = len(lidar_data) // 4
        front_end = 3 * len(lidar_data) // 4
        front_lidar = lidar_data[front_start:front_end]
        
        # Check minimum distance
        min_front_dist = np.min(front_lidar)
        if min_front_dist < self.obstacle_threshold:
            return True
        
        # Check for large gaps (overtaking opportunity)
        gap_threshold = self.gap_size_threshold
        gaps = []
        in_gap = False
        gap_start = None
        
        for i, dist in enumerate(front_lidar):
            if dist > gap_threshold:
                if not in_gap:
                    gap_start = i
                    in_gap = True
            else:
                if in_gap:
                    gap_size = i - gap_start
                    gaps.append(gap_size)
                    in_gap = False
        
        if in_gap:
            gap_size = len(front_lidar) - gap_start
            gaps.append(gap_size)
        
        # Use FollowGap if large gap detected
        if gaps and max(gaps) > len(front_lidar) * 0.3:
            return True
        
        # Use PurePursuit on straights (low curvature)
        if abs(track_curvature) < self.curvature_threshold:
            return False
        
        # Default: use PurePursuit
        return False
    
    def get_action(self, car, track_spline, lidar_data=None, track_curvature=0.0):
        """
        Get control action using hybrid controller.
        
        Args:
            car: CarState object
            track_spline: Track spline dict
            lidar_data: LiDAR scan array
            track_curvature: Current track curvature
        
        Returns:
            Action dict with 'motor' and 'steering', and 'controller_type'
        """
        # Generate observation
        observation = self.car_to_observation(car, track_spline, lidar_data)
        
        # Decide which controller to use
        use_follow_gap = self.should_use_follow_gap(lidar_data, track_curvature)
        
        if use_follow_gap:
            # Use FollowGap controller
            action = self.follow_gap.act(observation)
            self.current_controller_type = 'follow_gap'
        else:
            # Use PurePursuit controller
            state = self.generate_waypoint(car, track_spline)
            action = self.pure_pursuit.act(observation, state)
            self.current_controller_type = 'pure_pursuit'
        
        # Add controller type to action
        action['controller_type'] = self.current_controller_type
        
        return action
    
    def update_controller_params(self, controller_type, **kwargs):
        """
        Update parameters for a specific controller.
        
        Args:
            controller_type: 'follow_gap' or 'pure_pursuit'
            **kwargs: Parameters to update
        """
        if controller_type == 'follow_gap':
            self.follow_gap.update_params(**kwargs)
        elif controller_type == 'pure_pursuit':
            self.pure_pursuit.update_params(**kwargs)


class RacingLineController:
    """
    Enhanced controller that uses racing line optimization.
    Generates waypoints along optimal racing line instead of centerline.
    """
    
    def __init__(self, base_adapter, track_spline):
        """
        Initialize racing line controller.
        
        Args:
            base_adapter: ControllerAdapter instance
            track_spline: Track spline dict
        """
        self.base_adapter = base_adapter
        self.track_spline = track_spline
        self.racing_line_cache = {}
    
    def calculate_racing_line(self, curvature, speed):
        """
        Calculate optimal racing line offset from centerline.
        
        Args:
            curvature: Track curvature
            speed: Current speed
        
        Returns:
            Offset from centerline (positive = outside, negative = inside)
        """
        # Simplified racing line: late apex for slow corners, early for fast
        if abs(curvature) < 1e-6:
            return 0.0  # Straight: use centerline
        
        radius = 1.0 / abs(curvature)
        
        # Determine corner speed category
        if speed < 30:  # Slow corner
            # Late apex: start wide, cut inside
            offset = -radius * 0.3  # Inside
        elif speed < 60:  # Medium corner
            offset = -radius * 0.2  # Slightly inside
        else:  # Fast corner
            offset = radius * 0.1  # Slightly outside
        
        return offset
    
    def generate_racing_line_waypoint(self, car, lookahead_distance):
        """
        Generate waypoint along racing line.
        
        Args:
            car: CarState object
            lookahead_distance: Lookahead distance
        
        Returns:
            Waypoint dict
        """
        # Get position ahead
        s_ahead = car.s + lookahead_distance
        u_ahead = self.track_spline['s_to_u'](s_ahead)
        
        # Get centerline position
        pos_center = self.track_spline['pos'](u_ahead)[0]
        
        # Get curvature
        curvature = self.track_spline['curv'](u_ahead)
        
        # Calculate racing line offset
        offset = self.calculate_racing_line(curvature, car.v)
        
        # Calculate perpendicular direction
        u2 = self.track_spline['s_to_u'](s_ahead + 1.0)
        pos2 = self.track_spline['pos'](u2)[0]
        dx = pos2[0] - pos_center[0]
        dy = pos2[1] - pos_center[1]
        length = np.sqrt(dx**2 + dy**2)
        
        if length > 1e-6:
            # Perpendicular vector
            perp_x = -dy / length
            perp_y = dx / length
            
            # Apply offset
            waypoint_x = pos_center[0] + perp_x * offset
            waypoint_y = pos_center[1] + perp_y * offset
        else:
            waypoint_x = pos_center[0]
            waypoint_y = pos_center[1]
        
        waypoint = np.array([waypoint_x, waypoint_y, 0.0])
        return {'next_waypoint': waypoint}
    
    def get_action(self, car, track_spline, lidar_data=None, track_curvature=0.0):
        """
        Get action using racing line optimized PurePursuit.
        """
        # Check if we should use FollowGap for obstacles
        if lidar_data is not None:
            use_follow_gap = self.base_adapter.should_use_follow_gap(lidar_data, track_curvature)
            
            if use_follow_gap:
                observation = self.base_adapter.car_to_observation(car, track_spline, lidar_data)
                action = self.base_adapter.follow_gap.act(observation)
                action['controller_type'] = 'follow_gap'
                return action
        
        # Use racing line PurePursuit
        observation = self.base_adapter.car_to_observation(car, track_spline, lidar_data)
        state = self.generate_racing_line_waypoint(car, self.base_adapter.pure_pursuit.lookahead)
        action = self.base_adapter.pure_pursuit.act(observation, state)
        action['controller_type'] = 'racing_line'
        
        return action

