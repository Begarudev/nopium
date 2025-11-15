"""
2D LiDAR Simulator for F1 Race Simulation
Implements ray casting for track boundaries and car detection.
"""

import numpy as np
import math


class LidarSimulator:
    """2D LiDAR simulator using ray casting"""
    
    def __init__(self, num_rays=360, max_range=10.0, track_width=12.0):
        """
        Initialize LiDAR simulator.
        
        Args:
            num_rays: Number of LiDAR rays (default 360 for 1° resolution)
            max_range: Maximum detection range in meters
            track_width: Track width in meters (default 12m for F1)
        """
        self.num_rays = num_rays
        self.max_range = max_range
        self.track_width = track_width
        self.angles = np.linspace(0, 2 * np.pi, num_rays, endpoint=False)
        
    def generate_track_boundaries(self, track_spline, n_points=2000):
        """
        Generate left and right track boundaries from centerline spline.
        
        Args:
            track_spline: Track spline dict with 'pos' function
            n_points: Number of points along track
        
        Returns:
            left_boundary, right_boundary: Arrays of (x, y) points
        """
        ss = np.linspace(0, 1, n_points)
        centerline_points = track_spline['pos'](ss)
        
        left_boundary = []
        right_boundary = []
        
        for i in range(len(centerline_points)):
            # Get current point
            p = centerline_points[i]
            
            # Get next point for direction
            if i < len(centerline_points) - 1:
                p_next = centerline_points[i + 1]
            else:
                p_next = centerline_points[0]
            
            # Calculate direction vector
            dx = p_next[0] - p[0]
            dy = p_next[1] - p[1]
            length = np.sqrt(dx**2 + dy**2)
            
            if length > 1e-6:
                # Normalize
                dx /= length
                dy /= length
                
                # Perpendicular vector (rotate 90°)
                perp_x = -dy
                perp_y = dx
                
                # Offset by half track width
                offset = self.track_width / 2
                
                left_boundary.append([
                    p[0] + perp_x * offset,
                    p[1] + perp_y * offset
                ])
                right_boundary.append([
                    p[0] - perp_x * offset,
                    p[1] - perp_y * offset
                ])
            else:
                left_boundary.append([p[0], p[1]])
                right_boundary.append([p[0], p[1]])
        
        return np.array(left_boundary), np.array(right_boundary)
    
    def ray_line_intersection(self, ray_origin, ray_dir, line_start, line_end):
        """
        Check if ray intersects line segment.
        Returns distance to intersection or None if no intersection.
        """
        # Ray: origin + t * dir
        # Line: start + u * (end - start)
        
        line_dir = line_end - line_start
        
        # Check if parallel
        denom = ray_dir[0] * line_dir[1] - ray_dir[1] * line_dir[0]
        if abs(denom) < 1e-10:
            return None
        
        # Calculate intersection parameters
        diff = line_start - ray_origin
        t = (diff[0] * line_dir[1] - diff[1] * line_dir[0]) / denom
        u = (diff[0] * ray_dir[1] - diff[1] * ray_dir[0]) / denom
        
        # Check if intersection is valid
        if t < 0 or u < 0 or u > 1:
            return None
        
        return t
    
    def ray_circle_intersection(self, ray_origin, ray_dir, circle_center, circle_radius):
        """
        Check if ray intersects circle (for car detection).
        Returns distance to intersection or None.
        """
        # Vector from ray origin to circle center
        oc = circle_center - ray_origin
        
        # Project oc onto ray direction
        proj = np.dot(oc, ray_dir)
        
        # Distance from circle center to ray
        dist_sq = np.dot(oc, oc) - proj * proj
        
        # Check if ray misses circle
        if dist_sq > circle_radius ** 2:
            return None
        
        # Calculate intersection point
        half_chord = np.sqrt(circle_radius ** 2 - dist_sq)
        t1 = proj - half_chord
        t2 = proj + half_chord
        
        # Return closest intersection
        if t1 > 0:
            return t1
        elif t2 > 0:
            return t2
        
        return None
    
    def ray_polygon_intersection(self, ray_origin, ray_dir, polygon_points):
        """
        Check if ray intersects polygon (for car bounding box).
        Returns distance to intersection or None.
        """
        min_dist = None
        
        # Check intersection with each edge
        for i in range(len(polygon_points)):
            start = polygon_points[i]
            end = polygon_points[(i + 1) % len(polygon_points)]
            
            dist = self.ray_line_intersection(ray_origin, ray_dir, start, end)
            if dist is not None:
                if min_dist is None or dist < min_dist:
                    min_dist = dist
        
        return min_dist
    
    def get_car_bounding_box(self, car_x, car_y, car_angle, car_length=5.5, car_width=2.0):
        """
        Get bounding box vertices for a car.
        
        Args:
            car_x, car_y: Car position
            car_angle: Car heading angle
            car_length: Car length in meters
            car_width: Car width in meters
        
        Returns:
            Array of 4 corner vertices
        """
        # Half dimensions
        half_len = car_length / 2
        half_wid = car_width / 2
        
        # Local coordinates (car-aligned)
        corners_local = np.array([
            [half_len, half_wid],
            [-half_len, half_wid],
            [-half_len, -half_wid],
            [half_len, -half_wid]
        ])
        
        # Rotate and translate
        cos_a = np.cos(car_angle)
        sin_a = np.sin(car_angle)
        
        rotation_matrix = np.array([
            [cos_a, -sin_a],
            [sin_a, cos_a]
        ])
        
        corners_world = corners_local @ rotation_matrix.T
        corners_world[:, 0] += car_x
        corners_world[:, 1] += car_y
        
        return corners_world
    
    def cast_ray(self, ray_origin, ray_angle, obstacles):
        """
        Cast a single ray and return distance to nearest obstacle.
        
        Args:
            ray_origin: (x, y) starting point
            ray_angle: Angle in radians
            obstacles: List of obstacle dicts with 'type' and geometry
        
        Returns:
            Distance to nearest obstacle (or max_range if none)
        """
        ray_dir = np.array([np.cos(ray_angle), np.sin(ray_angle)])
        min_dist = self.max_range
        
        for obstacle in obstacles:
            dist = None
            
            if obstacle['type'] == 'line':
                dist = self.ray_line_intersection(
                    ray_origin, ray_dir,
                    obstacle['start'], obstacle['end']
                )
            elif obstacle['type'] == 'circle':
                dist = self.ray_circle_intersection(
                    ray_origin, ray_dir,
                    obstacle['center'], obstacle['radius']
                )
            elif obstacle['type'] == 'polygon':
                dist = self.ray_polygon_intersection(
                    ray_origin, ray_dir,
                    obstacle['vertices']
                )
            
            if dist is not None and dist < min_dist:
                min_dist = dist
        
        return min_dist
    
    def generate_lidar_scan(self, car_x, car_y, car_angle, track_spline, other_cars, 
                           track_boundaries=None):
        """
        Generate complete LiDAR scan for a car.
        
        Args:
            car_x, car_y: Car position
            car_angle: Car heading angle
            track_spline: Track spline dict
            other_cars: List of other car dicts with 'x', 'y', 'angle'
            track_boundaries: Pre-computed boundaries (optional)
        
        Returns:
            Array of distances (one per ray)
        """
        ray_origin = np.array([car_x, car_y])
        
        # Generate track boundaries if not provided
        if track_boundaries is None:
            left_boundary, right_boundary = self.generate_track_boundaries(track_spline)
        else:
            left_boundary, right_boundary = track_boundaries
        
        # Build obstacle list
        obstacles = []
        
        # Add track boundaries as line segments
        for i in range(len(left_boundary) - 1):
            obstacles.append({
                'type': 'line',
                'start': left_boundary[i],
                'end': left_boundary[i + 1]
            })
            obstacles.append({
                'type': 'line',
                'start': right_boundary[i],
                'end': right_boundary[i + 1]
            })
        
        # Close the loop
        if len(left_boundary) > 0:
            obstacles.append({
                'type': 'line',
                'start': left_boundary[-1],
                'end': left_boundary[0]
            })
            obstacles.append({
                'type': 'line',
                'start': right_boundary[-1],
                'end': right_boundary[0]
            })
        
        # Add other cars as bounding boxes
        for other_car in other_cars:
            if other_car['x'] == car_x and other_car['y'] == car_y:
                continue  # Skip self
            
            # Check if car is within range
            dx = other_car['x'] - car_x
            dy = other_car['y'] - car_y
            dist = np.sqrt(dx**2 + dy**2)
            
            if dist < self.max_range * 1.5:  # Slightly larger than max_range for safety
                bbox = self.get_car_bounding_box(
                    other_car['x'], other_car['y'], other_car['angle']
                )
                obstacles.append({
                    'type': 'polygon',
                    'vertices': bbox
                })
        
        # Cast all rays
        distances = []
        for angle_offset in self.angles:
            # Ray angle in world coordinates
            ray_angle = car_angle + angle_offset
            
            dist = self.cast_ray(ray_origin, ray_angle, obstacles)
            distances.append(dist)
        
        return np.array(distances)
    
    def generate_lidar_for_car(self, car, track_spline, all_cars, track_boundaries=None):
        """
        Convenience method to generate LiDAR for a CarState object.
        
        Args:
            car: CarState object
            track_spline: Track spline dict
            all_cars: List of all CarState objects
            track_boundaries: Pre-computed boundaries (optional)
        
        Returns:
            LiDAR scan array
        """
        # Get car position from track
        u = track_spline['s_to_u'](car.s)
        pos = track_spline['pos'](u)[0]
        car_x, car_y = pos[0], pos[1]
        
        # Calculate heading
        u2 = track_spline['s_to_u'](car.s + 1.0)
        pos2 = track_spline['pos'](u2)[0]
        car_angle = np.arctan2(pos2[1] - pos[1], pos2[0] - pos[0])
        
        # Prepare other cars list
        other_cars = []
        for other in all_cars:
            if other is car:
                continue
            
            u_other = track_spline['s_to_u'](other.s)
            pos_other = track_spline['pos'](u_other)[0]
            
            u2_other = track_spline['s_to_u'](other.s + 1.0)
            pos2_other = track_spline['pos'](u2_other)[0]
            angle_other = np.arctan2(pos2_other[1] - pos_other[1], 
                                     pos2_other[0] - pos_other[0])
            
            other_cars.append({
                'x': pos_other[0],
                'y': pos_other[1],
                'angle': angle_other
            })
        
        # Generate scan
        return self.generate_lidar_scan(
            car_x, car_y, car_angle, track_spline, other_cars, track_boundaries
        )

