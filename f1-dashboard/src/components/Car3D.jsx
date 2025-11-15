import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import { Html } from '@react-three/drei';
import * as THREE from 'three';

// Asset paths - Vite serves from assets folder (configured in vite.config.js)
const carModels = [
  '/f1_2020_williams_fw43/scene.gltf',
  '/f1_2021_alphatauri_at02/scene.gltf',
  '/f1_2021_haas_vf21/scene.gltf'
];

// Helper function to calculate proper track position and elevation for cars
// This uses interpolation along the track curve for smoother positioning
function getTrackPositionAndElevation(carX, carZ, trackData) {
  if (!trackData || !trackData.points || trackData.points.length === 0) {
    return { x: carX, y: 0.5, z: carZ }; // Default position and elevation
  }
  
  const points = trackData.points;
  
  // Find the two closest points to interpolate between
  let minDist1 = Infinity;
  let minDist2 = Infinity;
  let closestIdx1 = 0;
  let closestIdx2 = 0;
  
  for (let i = 0; i < points.length; i++) {
    const dx = points[i][0] - carX;
    const dz = points[i][1] - carZ;
    const dist = dx * dx + dz * dz;
    
    if (dist < minDist1) {
      minDist2 = minDist1;
      closestIdx2 = closestIdx1;
      minDist1 = dist;
      closestIdx1 = i;
    } else if (dist < minDist2) {
      minDist2 = dist;
      closestIdx2 = i;
    }
  }
  
  // Calculate elevation at both closest points
  const getElevation = (idx) => {
    return Math.abs(Math.sin(idx * 0.1) * 2) + Math.abs(Math.cos(idx * 0.05) * 1.5) + 0.5;
  };
  
  const elev1 = getElevation(closestIdx1);
  const elev2 = getElevation(closestIdx2);
  
  // Interpolate elevation based on distance weights
  const dist1 = Math.sqrt(minDist1);
  const dist2 = Math.sqrt(minDist2);
  const totalDist = dist1 + dist2;
  
  let elevation;
  if (totalDist > 0.001) {
    // Weighted average based on inverse distance
    const weight1 = dist2 / totalDist;
    const weight2 = dist1 / totalDist;
    elevation = elev1 * weight1 + elev2 * weight2;
  } else {
    elevation = elev1;
  }
  
  // Track width is 15 meters in TrackView3D, with 7.5m on each side from centerline
  // Allow a bit extra for racing line variations and spline interpolation differences
  const trackHalfWidth = 10; // Slightly wider than actual track for tolerance
  const distFromCenter = Math.sqrt(minDist1);
  
  if (distFromCenter > trackHalfWidth) {
    // Car appears to be off-track, gently nudge it back toward track
    // This helps with visual glitches from spline differences
    const trackPoint = points[closestIdx1];
    const dx = carX - trackPoint[0];
    const dz = carZ - trackPoint[1];
    const ratio = trackHalfWidth / distFromCenter;
    
    return {
      x: trackPoint[0] + dx * ratio,
      y: elevation,
      z: trackPoint[1] + dz * ratio
    };
  }
  
  // Car is on track, use its position as-is with interpolated elevation
  return { x: carX, y: elevation, z: carZ };
}

function Car3D({ car, isSelected, showLabel = false, trackData }) {
  const groupRef = useRef();
  
  // Distribute cars across all available models based on car name hash
  const modelPath = useMemo(() => {
    // Use hash of car name to consistently assign model
    const hash = car.name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    const modelIndex = Math.abs(hash) % carModels.length;
    return carModels[modelIndex];
  }, [car.name]);
  
  // Load the GLTF model - useGLTF must be called unconditionally
  // This will throw if model fails to load, which is handled by Suspense in parent
  const gltf = useGLTF(modelPath);
  const scene = gltf?.scene;
  
  // Clone the scene to avoid sharing geometry between instances
  const clonedScene = useMemo(() => {
    if (!scene) {
      console.warn(`Car model ${modelPath} scene is null`);
      return null;
    }
    const cloned = scene.clone();
    // Compute bounding box to determine scale and log for debugging
    const box = new THREE.Box3().setFromObject(cloned);
    box.expandByObject(cloned); // Ensure box includes all geometry
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    console.log(`Car model ${modelPath} loaded - Size:`, size, 'Center:', center, 'Box:', box);
    
    // Center the model at origin for easier positioning
    cloned.traverse((child) => {
      if (child.isMesh) {
      }
    });
    
    return cloned;
  }, [scene, modelPath]);
  
  // Apply car color to materials and enable shadows
  React.useEffect(() => {
    if (clonedScene) {
      clonedScene.traverse((child) => {
        if (child.isMesh) {
          // Enable shadows
          child.castShadow = true;
          child.receiveShadow = true;
          
          // Apply car color
          if (child.material) {
            const color = new THREE.Color(car.color || '#ffffff');
            if (Array.isArray(child.material)) {
              child.material = child.material.map(mat => {
                const newMat = mat.clone();
                newMat.color = color;
                newMat.metalness = 0.3;
                newMat.roughness = 0.4;
                return newMat;
              });
            } else {
              child.material = child.material.clone();
              child.material.color = color;
              child.material.metalness = 0.3;
              child.material.roughness = 0.4;
            }
          }
        }
      });
    }
  }, [clonedScene, car.color]);
  
  // Smooth position interpolation
  // Map 2D coordinates to 3D: car.x -> x, car.y -> z, elevation -> y
  const targetPosition = useRef(new THREE.Vector3(car.x, 0, car.y));
  const currentPosition = useRef(new THREE.Vector3(car.x, 0, car.y));
  const previousPosition = useRef(new THREE.Vector3(car.x, 0, car.y));
  const targetRotation = useRef(car.angle || 0);
  const currentRotation = useRef(car.angle || 0);
  const isInitialized = useRef(false);
  
  useFrame((state, delta) => {
    if (!groupRef.current) return;
    
    // Store previous position before updating
    previousPosition.current.copy(targetPosition.current);
    
    // Get proper track position and elevation for the car
    const trackPos = getTrackPositionAndElevation(car.x, car.y, trackData);
    
    // Add offset to place car above the track surface (not inside it)
    const carHeightOffset = 0.8; // Half the height of a typical F1 car
    
    // Update target position (2D x,y -> 3D x,z with y as elevation)
    targetPosition.current.set(trackPos.x, trackPos.y + carHeightOffset, trackPos.z);
    
    // Calculate rotation based on actual movement direction in 3D
    // This ensures the car faces where it's actually moving
    const deltaX = targetPosition.current.x - previousPosition.current.x;
    const deltaZ = targetPosition.current.z - previousPosition.current.z;
    const movementDistance = Math.sqrt(deltaX * deltaX + deltaZ * deltaZ);
    
    // Use car.angle as the primary source of truth for direction
    // Only calculate from movement if angle isn't provided or as fallback
    if (car.angle !== undefined && car.angle !== null) {
      // Convert car.angle (from server) to Three.js rotation
      // Server angle is typically in standard math convention (0 = right, counterclockwise positive)
      // Three.js Y rotation: 0 = forward along +Z, counterclockwise positive
      // Adjust as needed: add -PI/2 to convert from 0=right to 0=forward
      targetRotation.current = -car.angle + Math.PI / 2;
    } else if (movementDistance > 0.01) {
      // Fallback: calculate angle from movement vector in 3D space
      // atan2(deltaZ, deltaX) gives us the angle of movement
      // Adjust to make car face forward in the direction of movement
      targetRotation.current = Math.atan2(deltaZ, deltaX) + Math.PI / 2;
    }
    
    // Initialize rotation on first frame to prevent spinning from 0
    if (!isInitialized.current) {
      currentRotation.current = targetRotation.current;
      currentPosition.current.copy(targetPosition.current);
      isInitialized.current = true;
    }
    
    // Calculate speed-adaptive interpolation factor
    // Distance between current and target position
    const distance = currentPosition.current.distanceTo(targetPosition.current);
    // Base interpolation factor, increases with distance (speed)
    // At low speeds (small distance): slower interpolation for smoothness
    // At high speeds (large distance): faster interpolation to prevent lag
    const baseInterpolation = 0.2;
    const speedFactor = Math.min(distance / 10, 1.5); // Cap at 1.5x
    const positionLerpFactor = Math.min(baseInterpolation + speedFactor * 0.15, 0.6);
    
    // Smooth interpolation with speed-adaptive factor
    currentPosition.current.lerp(targetPosition.current, positionLerpFactor);
    
    // Handle rotation interpolation with wrap-around
    const angleDiff = targetRotation.current - currentRotation.current;
    // Normalize angle difference to [-PI, PI] for shortest rotation
    let normalizedDiff = ((angleDiff + Math.PI) % (2 * Math.PI)) - Math.PI;
    // Use adaptive rotation speed based on turn sharpness
    const rotationSpeed = movementDistance > 0.01 ? Math.min(0.4, Math.abs(normalizedDiff) * 2) : 0.2;
    currentRotation.current += normalizedDiff * rotationSpeed;
    
    // Apply position and rotation
    groupRef.current.position.copy(currentPosition.current);
    groupRef.current.rotation.y = currentRotation.current;
    
    // Scale based on selection
    const targetScale = isSelected ? 1.1 : 1.0;
    groupRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
  });
  
  // If model failed to load, show placeholder
  if (!clonedScene) {
    const trackPos = getTrackPositionAndElevation(car.x, car.y, trackData);
    const carHeightOffset = 0.8;
    return (
      <group ref={groupRef} position={[trackPos.x, trackPos.y + carHeightOffset, trackPos.z]}>
        <mesh>
          <boxGeometry args={[5 * 2.5, 1.5 * 2.5, 2 * 2.5]} />
          <meshStandardMaterial color={car.color || '#ff0000'} />
        </mesh>
        {car.position !== undefined && (
          <Html position={[0, 3, 0]} center>
            <div style={{ background: 'rgba(0, 0, 0, 0.7)', color: '#ffffff', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 'bold' }}>
              P{car.position} {car.name} (Loading...)
            </div>
          </Html>
        )}
      </group>
    );
  }
  
  // Calculate scale based on model size
  // F1 cars are ~5.5m long, so if model is in different units, scale accordingly
  // Most GLTF models are in meters, so scale of 1 should work
  // If model is too small/large, adjust this value
  const scale = 1;
  
  // Calculate auto-scale based on model bounding box
  const autoScale = useMemo(() => {
    if (!clonedScene) return 1;
    const box = new THREE.Box3().setFromObject(clonedScene);
    box.expandByObject(clonedScene);
    const size = box.getSize(new THREE.Vector3());
    // F1 car is ~5.5m long, scale model to match, then make it 2.5x bigger for better visibility
    const targetLength = 5.5 * 2.5; // Make cars 2.5x bigger
    const maxDimension = Math.max(Math.abs(size.x), Math.abs(size.y), Math.abs(size.z));
    console.log(`Car ${car.name} - Model dimensions:`, size, 'Max:', maxDimension, 'Calculated scale:', maxDimension > 0 ? targetLength / maxDimension : 1);
    if (maxDimension > 0 && maxDimension < 1000) { // Sanity check
      const scale = targetLength / maxDimension;
      return scale;
    }
    // If model seems wrong size, use default
    return 4.5; // Default scale multiplier
  }, [clonedScene, car.name]);
  
  return (
    <group ref={groupRef} castShadow receiveShadow>
      <primitive 
        object={clonedScene} 
        scale={autoScale}
        castShadow
        receiveShadow
        // No initial rotation - let the car.angle control the direction
        // If models face wrong direction by default, adjust this
        rotation={[0, 0, 0]}
      />
      
      {/* Position label - only show if enabled */}
      {showLabel && car.position !== undefined && (
        <Html
          position={[0, 3, 0]}
          center
          style={{
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        >
          <div
            style={{
              background: 'rgba(0, 0, 0, 0.7)',
              color: '#ffffff',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 'bold',
              whiteSpace: 'nowrap',
            }}
          >
            P{car.position} {car.name}
          </div>
        </Html>
      )}
      
      {/* Selection highlight */}
      {isSelected && (
        <mesh position={[0, 0, 0]}>
          <ringGeometry args={[2, 2.5, 32]} />
          <meshBasicMaterial color="#ffff00" transparent opacity={0.5} />
        </mesh>
      )}
    </group>
  );
}

export default React.memo(Car3D);

