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

function Car3D({ car, isSelected }) {
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
  
  // Apply car color to materials
  React.useEffect(() => {
    if (clonedScene) {
      clonedScene.traverse((child) => {
        if (child.isMesh && child.material) {
          // Create a new material with the car color
          const color = new THREE.Color(car.color || '#ffffff');
          if (Array.isArray(child.material)) {
            child.material = child.material.map(mat => {
              const newMat = mat.clone();
              newMat.color = color;
              return newMat;
            });
          } else {
            child.material = child.material.clone();
            child.material.color = color;
          }
        }
      });
    }
  }, [clonedScene, car.color]);
  
  // Smooth position interpolation
  // Map 2D coordinates to 3D: car.x -> x, car.y -> z, elevation -> y
  const targetPosition = useRef(new THREE.Vector3(car.x, 0, car.y));
  const currentPosition = useRef(new THREE.Vector3(car.x, 0, car.y));
  const targetRotation = useRef(0);
  const currentRotation = useRef(0);
  
  useFrame((state, delta) => {
    if (!groupRef.current) return;
    
    // Update target position (2D x,y -> 3D x,z with y as elevation)
    targetPosition.current.set(car.x, 0, car.y);
    // car.angle is from atan2(dy, dx) which gives direction in 2D (x,y) plane
    // In 3D, we map (x,y) -> (x,z), so angle needs to be applied to Y rotation
    // atan2 gives: 0 = +x, π/2 = +y, π = -x, -π/2 = -y
    // In 3D: 0 = +x, π/2 = +z, π = -x, -π/2 = -z
    // Car models are oriented 90 degrees off, so add π/2 to correct the direction
    targetRotation.current = (car.angle || 0) + Math.PI / 2;
    
    // Smooth interpolation
    currentPosition.current.lerp(targetPosition.current, 0.1);
    const angleDiff = targetRotation.current - currentRotation.current;
    // Normalize angle difference to [-PI, PI] for shortest rotation
    let normalizedDiff = ((angleDiff + Math.PI) % (2 * Math.PI)) - Math.PI;
    currentRotation.current += normalizedDiff * 0.1;
    
    // Apply position and rotation
    groupRef.current.position.copy(currentPosition.current);
    // Apply the rotation - car.angle is already the correct direction
    groupRef.current.rotation.y = currentRotation.current;
    
    // Scale based on selection
    const targetScale = isSelected ? 1.1 : 1.0;
    groupRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
  });
  
  // If model failed to load, show placeholder
  if (!clonedScene) {
    return (
      <group ref={groupRef} position={[car.x, 0, car.y]}>
        <mesh>
          <boxGeometry args={[5, 1.5, 2]} />
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
    // F1 car is ~5.5m long, scale model to match
    const targetLength = 5.5;
    const maxDimension = Math.max(Math.abs(size.x), Math.abs(size.y), Math.abs(size.z));
    console.log(`Car ${car.name} - Model dimensions:`, size, 'Max:', maxDimension, 'Calculated scale:', maxDimension > 0 ? targetLength / maxDimension : 1);
    if (maxDimension > 0 && maxDimension < 1000) { // Sanity check
      const scale = targetLength / maxDimension;
      return scale;
    }
    // If model seems wrong size, use default
    return 1;
  }, [clonedScene, car.name]);
  
  return (
    <group ref={groupRef}>
      <primitive 
        object={clonedScene} 
        scale={autoScale}
        // No initial rotation - let the car.angle control the direction
        // If models face wrong direction by default, adjust this
        rotation={[0, 0, 0]}
      />
      
      {/* Position label */}
      {car.position !== undefined && (
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

