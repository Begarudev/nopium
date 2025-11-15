import React, { useRef, useMemo, useState, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Environment } from '@react-three/drei';
import * as THREE from 'three';
import Car3D from './Car3D';
import './TrackView3D.css';

// Track component that creates 3D geometry from 2D points
function Track3D({ trackData, followCar, cars }) {
  const trackMeshRef = useRef();
  const kerbsRef = useRef();
  const barriersRef = useRef();
  
  // Convert 2D track points to 3D spline
  const trackGeometry = useMemo(() => {
    if (!trackData || !trackData.points || trackData.points.length === 0) {
      return null;
    }
    
    const points = trackData.points;
    
    // Create 3D points with elevation variation
    // Map 2D (x, y) to 3D (x, elevation, z) where Y is up in Three.js
    const threePoints = points.map((p, i) => {
      const x = p[0];
      const z = p[1]; // 2D y becomes 3D z
      // Add elevation based on position (simulate hills and dips)
      const y = Math.sin(i * 0.1) * 2 + Math.cos(i * 0.05) * 3;
      return new THREE.Vector3(x, y, z);
    });
    
    // Create closed spline
    const closedPoints = [...threePoints, threePoints[0]];
    const curve = new THREE.CatmullRomCurve3(closedPoints, true);
    
    // Extrude track along the curve
    const trackWidth = 12; // F1 track width in meters
    const shape = new THREE.Shape();
    shape.moveTo(-trackWidth / 2, 0);
    shape.lineTo(trackWidth / 2, 0);
    shape.lineTo(trackWidth / 2, 0.1);
    shape.lineTo(-trackWidth / 2, 0.1);
    shape.lineTo(-trackWidth / 2, 0);
    
    const extrudeSettings = {
      steps: 100,
      bevelEnabled: false,
      extrudePath: curve,
    };
    
    const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    return geometry;
  }, [trackData]);
  
  // Create kerbs geometries (one for each side)
  const kerbsGeometries = useMemo(() => {
    if (!trackData || !trackData.points || trackData.points.length === 0) {
      return [];
    }
    
    const points = trackData.points;
    const kerbWidth = 0.3;
    const kerbHeight = 0.15;
    
    const geometries = [];
    
    // Inner and outer kerbs
    for (let side = 0; side < 2; side++) {
      const offset = side === 0 ? -6 : 6; // Offset from track center
      const threePoints = points.map((p, i) => {
        const x = p[0];
        const z = p[1]; // 2D y becomes 3D z
        const y = Math.sin(i * 0.1) * 2 + Math.cos(i * 0.05) * 3; // elevation
        // Calculate perpendicular offset
        const nextIdx = (i + 1) % points.length;
        const dx = points[nextIdx][0] - p[0];
        const dz = points[nextIdx][1] - p[1];
        const len = Math.sqrt(dx * dx + dz * dz);
        const perpX = -dz / len * offset;
        const perpZ = dx / len * offset;
        return new THREE.Vector3(x + perpX, y, z + perpZ);
      });
      
      const closedPoints = [...threePoints, threePoints[0]];
      const curve = new THREE.CatmullRomCurve3(closedPoints, true);
      
      const shape = new THREE.Shape();
      shape.moveTo(-kerbWidth / 2, 0);
      shape.lineTo(kerbWidth / 2, 0);
      shape.lineTo(kerbWidth / 2, kerbHeight);
      shape.lineTo(-kerbWidth / 2, kerbHeight);
      shape.lineTo(-kerbWidth / 2, 0);
      
      const extrudeSettings = {
        steps: 100,
        bevelEnabled: false,
        extrudePath: curve,
      };
      
      geometries.push(new THREE.ExtrudeGeometry(shape, extrudeSettings));
    }
    
    return geometries;
  }, [trackData]);
  
  // Track material - brighter for visibility
  const trackMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: '#4a4a4a',
      roughness: 0.8,
      metalness: 0.1,
      side: THREE.DoubleSide,
    });
  }, []);
  
  // Kerbs material (red/white stripes)
  const kerbsMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: '#ff4444',
      roughness: 0.7,
    });
  }, []);
  
  return (
    <>
      {/* Track surface */}
      {trackGeometry && (
        <mesh ref={trackMeshRef} geometry={trackGeometry} material={trackMaterial} />
      )}
      
      {/* Kerbs - render each side separately */}
      {kerbsGeometries.map((geometry, idx) => (
        <mesh key={idx} geometry={geometry} material={kerbsMaterial} />
      ))}
      
      {/* Ground plane */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.5, 0]}>
        <planeGeometry args={[5000, 5000]} />
        <meshStandardMaterial color="#1a1f3a" />
      </mesh>
    </>
  );
}

// Camera controller that follows a car
function CameraController({ followCar, cars, isFollowing, trackCenter }) {
  const cameraRef = useRef();
  const controlsRef = useRef();
  
  useFrame(() => {
    if (isFollowing && followCar && cars && cars.length > 0) {
      const car = cars.find(c => c.name === followCar);
      if (car && cameraRef.current && controlsRef.current) {
        // Follow car from behind and above
        // Map 2D coordinates: car.x -> 3D x, car.y -> 3D z
        const offsetX = Math.cos(car.angle) * 30;
        const offsetY = 25;
        const offsetZ = Math.sin(car.angle) * 30;
        
        const targetX = car.x + offsetX;
        const targetY = offsetY;
        const targetZ = car.y + offsetZ;
        
        // Smooth camera movement
        cameraRef.current.position.lerp(
          new THREE.Vector3(targetX, targetY, targetZ),
          0.05
        );
        
        // Look at car (map 2D to 3D: x->x, y->z, elevation->y)
        controlsRef.current.target.lerp(
          new THREE.Vector3(car.x, 0, car.y),
          0.05
        );
      } else if (!isFollowing && controlsRef.current && trackCenter) {
        // Default: look at track center
        controlsRef.current.target.lerp(
          new THREE.Vector3(trackCenter[0], 0, trackCenter[1]),
          0.05
        );
      }
    }
  });
  
  return (
    <>
      <PerspectiveCamera
        ref={cameraRef}
        makeDefault
        fov={50}
      />
      <OrbitControls
        ref={controlsRef}
        enablePan={true}
        enableZoom={true}
        minDistance={50}
        maxDistance={2000}
        maxPolarAngle={Math.PI / 1.8}
        target={trackCenter ? [trackCenter[0], 0, trackCenter[1]] : [0, 0, 0]}
      />
    </>
  );
}

const TrackView3D = ({ trackData, cars = [], followCar, onCarClick }) => {
  const [isFollowing, setIsFollowing] = useState(!!followCar);
  
  React.useEffect(() => {
    setIsFollowing(!!followCar);
  }, [followCar]);
  
  // Calculate center and bounds of track for initial camera position
  const trackBounds = useMemo(() => {
    if (!trackData || !trackData.points || trackData.points.length === 0) {
      return { center: [0, 0], size: [1000, 1000] };
    }
    const points = trackData.points;
    const xs = points.map(p => p[0]);
    const ys = points.map(p => p[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const sizeX = maxX - minX;
    const sizeY = maxY - minY;
    return { 
      center: [centerX, centerY], 
      size: [sizeX, sizeY],
      min: [minX, minY],
      max: [maxX, maxY]
    };
  }, [trackData]);
  
  // Calculate camera distance based on track size
  const cameraDistance = useMemo(() => {
    const maxSize = Math.max(trackBounds.size[0], trackBounds.size[1]);
    return Math.max(maxSize * 0.8, 200);
  }, [trackBounds]);
  
  return (
    <div className="track-view-3d">
      <Canvas
        gl={{ antialias: true, alpha: false }}
        camera={{ 
          position: [
            trackBounds.center[0], 
            cameraDistance * 0.5, 
            trackBounds.center[1] + cameraDistance
          ], 
          fov: 50 
        }}
        style={{ width: '100%', height: '100%' }}
      >
        {/* Lighting - increased intensity */}
        <ambientLight intensity={0.6} />
        <directionalLight position={[trackBounds.center[0] + 200, 200, trackBounds.center[1] + 200]} intensity={1.2} castShadow />
        <directionalLight position={[trackBounds.center[0] - 200, 100, trackBounds.center[1] - 200]} intensity={0.5} />
        <pointLight position={[trackBounds.center[0], 100, trackBounds.center[1]]} intensity={0.5} />
        
        {/* Environment for better lighting */}
        <Environment preset="sunset" />
        
        {/* Camera and controls */}
        <CameraController 
          followCar={followCar} 
          cars={cars} 
          isFollowing={isFollowing}
          trackCenter={trackBounds.center}
        />
        
        {/* Helper grid for debugging */}
        <gridHelper args={[Math.max(trackBounds.size[0], trackBounds.size[1]) * 1.5, 20, '#444444', '#222222']} position={[trackBounds.center[0], 0, trackBounds.center[1]]} />
        
        {/* Track */}
        {trackData && trackData.points && trackData.points.length > 0 && (
          <Track3D trackData={trackData} followCar={followCar} cars={cars} />
        )}
        
        {/* Cars */}
        <Suspense fallback={null}>
          {cars && cars.length > 0 && cars.map((car, idx) => (
            car && car.x !== undefined && car.y !== undefined && (
              <Car3D
                key={car.name || idx}
                car={car}
                isSelected={followCar === car.name}
              />
            )
          ))}
        </Suspense>
      </Canvas>
    </div>
  );
};

export default TrackView3D;

