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
  
  // Convert 2D track points to 3D spline using TubeGeometry
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
      // Keep all elevation positive to stay above ground
      const y = Math.abs(Math.sin(i * 0.1) * 2) + Math.abs(Math.cos(i * 0.05) * 1.5) + 0.5;
      return new THREE.Vector3(x, y, z);
    });
    
    // Create closed spline
    const closedPoints = [...threePoints, threePoints[0]];
    const curve = new THREE.CatmullRomCurve3(closedPoints, true);
    
    // Create a flat ribbon geometry for the track using custom geometry
    const segments = 200; // Number of segments along the curve
    const trackWidth = 15; // F1 track width in meters (12-15m is typical)
    
    const geometry = new THREE.BufferGeometry();
    const vertices = [];
    const indices = [];
    const normals = [];
    const uvs = [];
    
    // Generate vertices along the curve
    for (let i = 0; i <= segments; i++) {
      const t = i / segments;
      const point = curve.getPointAt(t);
      const tangent = curve.getTangentAt(t).normalize();
      
      // Calculate perpendicular vector (binormal) for track width
      // Use a consistent up vector to prevent twisting
      const up = new THREE.Vector3(0, 1, 0);
      const binormal = new THREE.Vector3().crossVectors(up, tangent).normalize();
      
      // Create left and right edge points
      const left = point.clone().add(binormal.clone().multiplyScalar(trackWidth / 2));
      const right = point.clone().add(binormal.clone().multiplyScalar(-trackWidth / 2));
      
      vertices.push(left.x, left.y, left.z);
      vertices.push(right.x, right.y, right.z);
      
      // Calculate normals (pointing up)
      normals.push(0, 1, 0);
      normals.push(0, 1, 0);
      
      // UVs for texture mapping
      uvs.push(0, t);
      uvs.push(1, t);
      
      // Create triangles (except for last iteration)
      if (i < segments) {
        const base = i * 2;
        // First triangle
        indices.push(base, base + 1, base + 2);
        // Second triangle
        indices.push(base + 1, base + 3, base + 2);
      }
    }
    
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
    geometry.setIndex(indices);
    
    return geometry;
  }, [trackData]);
  
  // Create kerbs geometries (one for each side) using ribbon geometry
  const kerbsGeometries = useMemo(() => {
    if (!trackData || !trackData.points || trackData.points.length === 0) {
      return [];
    }
    
    const points = trackData.points;
    const kerbWidth = 0.5;
    const kerbHeight = 0.15;
    const segments = 200;
    
    // Create 3D points for track center curve
    const threePoints = points.map((p, i) => {
      const x = p[0];
      const z = p[1];
      // Keep all elevation positive to stay above ground
      const y = Math.abs(Math.sin(i * 0.1) * 2) + Math.abs(Math.cos(i * 0.05) * 1.5) + 0.5;
      return new THREE.Vector3(x, y, z);
    });
    
    const closedPoints = [...threePoints, threePoints[0]];
    const curve = new THREE.CatmullRomCurve3(closedPoints, true);
    
    const geometries = [];
    
    // Inner and outer kerbs
    for (let side = 0; side < 2; side++) {
      const offset = side === 0 ? -8.0 : 8.0; // Offset from track center (track is 15m wide)
      
      const geometry = new THREE.BufferGeometry();
      const vertices = [];
      const indices = [];
      const normals = [];
      const uvs = [];
      
      // Generate vertices along the curve
      for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        const point = curve.getPointAt(t);
        const tangent = curve.getTangentAt(t).normalize();
        
        // Calculate perpendicular vector
        const up = new THREE.Vector3(0, 1, 0);
        const binormal = new THREE.Vector3().crossVectors(up, tangent).normalize();
        
        // Offset point to kerb position
        const kerbCenter = point.clone().add(binormal.clone().multiplyScalar(offset));
        
        // Create inner and outer edge points for kerb width
        const inner = kerbCenter.clone().add(binormal.clone().multiplyScalar(-kerbWidth / 2));
        const outer = kerbCenter.clone().add(binormal.clone().multiplyScalar(kerbWidth / 2));
        
        // Raise kerb slightly above track
        inner.y += kerbHeight;
        outer.y += kerbHeight;
        
        vertices.push(inner.x, inner.y, inner.z);
        vertices.push(outer.x, outer.y, outer.z);
        
        // Normals pointing up
        normals.push(0, 1, 0);
        normals.push(0, 1, 0);
        
        // UVs for striped texture
        uvs.push(0, t * 20); // Multiply for repeating stripes
        uvs.push(1, t * 20);
        
        // Create triangles
        if (i < segments) {
          const base = i * 2;
          indices.push(base, base + 1, base + 2);
          indices.push(base + 1, base + 3, base + 2);
        }
      }
      
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
      geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
      geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
      geometry.setIndex(indices);
      
      geometries.push(geometry);
    }
    
    return geometries;
  }, [trackData]);
  
  // Track material - realistic asphalt
  const trackMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: '#2a2a2a',
      roughness: 0.9,
      metalness: 0.0,
      side: THREE.DoubleSide,
    });
  }, []);
  
  // Kerbs material (red/white stripes)
  const kerbsMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: '#e31b23',
      roughness: 0.6,
      metalness: 0.0,
    });
  }, []);
  
  // Grass material for surrounding area
  const grassMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: '#2a5020',
      roughness: 1.0,
      metalness: 0.0,
    });
  }, []);
  
  return (
    <>
      {/* Track surface */}
      {trackGeometry && (
        <mesh ref={trackMeshRef} geometry={trackGeometry} material={trackMaterial} castShadow receiveShadow />
      )}
      
      {/* Kerbs - render each side separately */}
      {kerbsGeometries.map((geometry, idx) => (
        <mesh key={idx} geometry={geometry} material={kerbsMaterial} castShadow receiveShadow />
      ))}
      
      {/* Ground plane - grass */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.5, 0]} receiveShadow>
        <planeGeometry args={[5000, 5000]} />
        <meshStandardMaterial color="#2a5020" roughness={1.0} />
      </mesh>
      
      {/* Sky dome */}
      <mesh>
        <sphereGeometry args={[2500, 32, 32]} />
        <meshBasicMaterial color="#87CEEB" side={THREE.BackSide} />
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
        enableDamping={true}
        dampingFactor={0.08}
        rotateSpeed={0.5}
        zoomSpeed={0.8}
        minDistance={40}
        maxDistance={2500}
        maxPolarAngle={Math.PI / 2.05}
        minPolarAngle={Math.PI / 8}
        target={trackCenter ? [trackCenter[0], 0, trackCenter[1]] : [0, 0, 0]}
      />
    </>
  );
}

const TrackView3D = ({ trackData, cars = [], followCar, onCarClick }) => {
  const [isFollowing, setIsFollowing] = useState(!!followCar);
  const [showLabels, setShowLabels] = useState(false);
  
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
    return Math.max(maxSize * 0.55, 150);
  }, [trackBounds]);
  
  // Better initial camera position - TV broadcast style angle
  const initialCameraPosition = useMemo(() => {
    // Position camera at a 35-45 degree angle for dramatic view
    const horizontalDistance = cameraDistance * 0.7;
    const height = cameraDistance * 0.35;
    const angle = Math.PI / 4; // 45 degrees
    
    return [
      trackBounds.center[0] + Math.cos(angle) * horizontalDistance,
      height,
      trackBounds.center[1] + Math.sin(angle) * horizontalDistance
    ];
  }, [trackBounds, cameraDistance]);
  
  return (
    <div className="track-view-3d">
      {/* Toggle button for car labels */}
      <button 
        className="labels-toggle-btn"
        onClick={() => setShowLabels(!showLabels)}
        title={showLabels ? "Hide car labels" : "Show car labels"}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 7h18M3 12h18M3 17h18" />
          {!showLabels && <line x1="3" y1="3" x2="21" y2="21" strokeWidth="2" />}
        </svg>
        {showLabels ? 'Hide Labels' : 'Show Labels'}
      </button>
      <Canvas
        shadows
        gl={{ 
          antialias: true, 
          alpha: false,
          powerPreference: "high-performance",
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.2
        }}
        camera={{ 
          position: initialCameraPosition,
          fov: 65,
          near: 0.1,
          far: 5000
        }}
        style={{ width: '100%', height: '100%' }}
      >
        {/* Realistic lighting setup */}
        <ambientLight intensity={0.4} />
        
        {/* Main sun light */}
        <directionalLight 
          position={[trackBounds.center[0] + 400, 300, trackBounds.center[1] + 300]} 
          intensity={1.5}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-far={1000}
          shadow-camera-left={-500}
          shadow-camera-right={500}
          shadow-camera-top={500}
          shadow-camera-bottom={-500}
          shadow-bias={-0.0001}
        />
        
        {/* Fill light */}
        <directionalLight 
          position={[trackBounds.center[0] - 300, 150, trackBounds.center[1] - 200]} 
          intensity={0.3}
        />
        
        {/* Hemisphere light for sky/ground ambient */}
        <hemisphereLight
          color="#ffffff"
          groundColor="#444444"
          intensity={0.5}
        />
        
        {/* Environment for realistic reflections */}
        <Environment preset="city" background={false} />
        
        {/* Camera and controls */}
        <CameraController 
          followCar={followCar} 
          cars={cars} 
          isFollowing={isFollowing}
          trackCenter={trackBounds.center}
        />
        
        {/* Subtle grid helper */}
        <gridHelper 
          args={[Math.max(trackBounds.size[0], trackBounds.size[1]) * 1.5, 30, '#333333', '#222222']} 
          position={[trackBounds.center[0], -0.4, trackBounds.center[1]]} 
        />
        
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
                showLabel={showLabels}
                trackData={trackData}
              />
            )
          ))}
        </Suspense>
      </Canvas>
    </div>
  );
};

export default TrackView3D;

