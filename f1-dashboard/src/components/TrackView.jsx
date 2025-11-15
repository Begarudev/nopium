import React, { useRef, useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ZoomIn, ZoomOut, Maximize2, Minimize2, Box, Square } from 'lucide-react';
import { checkeredFlag, racingSpotlight, speedStreak, tireMarks } from '../utils/animations';
import TrackView3D from './TrackView3D';
import './TrackView.css';

const TrackView = ({ trackData, cars = [], onCarClick }) => {
  const canvasRef = useRef(null);
  const animationFrameRef = useRef(null);
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [followCar, setFollowCar] = useState(null);
  const [showLidar, setShowLidar] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [is3DView, setIs3DView] = useState(false);
  const carTrailsRef = useRef(new Map());
  const trackViewRef = useRef(null);
  const finishLineRef = useRef(null);
  const checkeredFlagRef = useRef(null);
  const prevCarAnglesRef = useRef(new Map());
  const tireMarkPositionsRef = useRef([]);
  const prevLapRef = useRef(0);

  // Smooth interpolation for car positions
  const [interpolatedCars, setInterpolatedCars] = useState(cars || []);
  const prevCarsRef = useRef(cars || []);

  useEffect(() => {
    if (cars && cars.length > 0) {
      // Interpolate car positions for smooth animation
      const interpolated = cars.map((car, idx) => {
        const prevCar = prevCarsRef.current[idx];
        if (prevCar && prevCar.x === car.x && prevCar.y === car.y) {
          return car;
        }
        return car;
      });
      setInterpolatedCars(interpolated);
      
      // Detect sharp turns for tire marks
      cars.forEach(car => {
        const prevAngle = prevCarAnglesRef.current.get(car.name);
        if (prevAngle !== undefined && car.angle !== undefined) {
          const angleDiff = Math.abs(car.angle - prevAngle);
          // If angle change is significant (sharp turn)
          if (angleDiff > 0.3 && car.speed > 100) {
            // Store tire mark position (will be drawn on canvas)
            tireMarkPositionsRef.current.push({
              x: car.x,
              y: car.y,
              angle: car.angle,
              color: car.color,
              time: Date.now()
            });
            // Keep only recent tire marks
            const now = Date.now();
            tireMarkPositionsRef.current = tireMarkPositionsRef.current.filter(
              mark => now - mark.time < 5000
            );
          }
        }
        prevCarAnglesRef.current.set(car.name, car.angle);
      });
      
      prevCarsRef.current = cars;
    }
  }, [cars]);

  // Checkered flag animation at top of track map when lap changes
  useEffect(() => {
    if (checkeredFlagRef.current && cars && cars.length > 0) {
      const maxLap = Math.max(...cars.map(c => c.laps || 0));
      
      if (maxLap > prevLapRef.current && maxLap > 0) {
        checkeredFlag(checkeredFlagRef.current, {
          duration: 1000,
          size: 20,
          colors: ['#FFFFFF', '#000000'],
          lapNumber: maxLap
        });
      }
      prevLapRef.current = maxLap;
    }
  }, [cars]);

  // Racing spotlight for selected car
  useEffect(() => {
    if (followCar && trackViewRef.current) {
      const spotlightElement = document.createElement('div');
      spotlightElement.className = 'car-spotlight';
      trackViewRef.current.appendChild(spotlightElement);
      const animation = racingSpotlight(spotlightElement, {
        duration: 2000,
        color: '#FFD700'
      });
      
      return () => {
        animation.pause();
        if (spotlightElement.parentNode) {
          spotlightElement.parentNode.removeChild(spotlightElement);
        }
      };
    }
  }, [followCar]);

  const drawTrack = useCallback((ctx, transform, points) => {
    // Draw track surface with gradient
    const gradient = ctx.createLinearGradient(0, 0, ctx.canvas.width, ctx.canvas.height);
    gradient.addColorStop(0, '#1a1f3a');
    gradient.addColorStop(1, '#0f1425');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);

    // Draw track boundaries (kerbs)
    ctx.strokeStyle = '#2a3f5f';
    ctx.lineWidth = 45;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    points.forEach((p, i) => {
      const [x, y] = transform(p[0], p[1]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.stroke();

    // Draw kerbs (red/white stripes) - simplified
    ctx.strokeStyle = '#ff4444';
    ctx.lineWidth = 3;
    ctx.setLineDash([8, 4]);
    ctx.beginPath();
    points.forEach((p, i) => {
      const [x, y] = transform(p[0], p[1]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw track centerline
    ctx.strokeStyle = '#4a6fa5';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    points.forEach((p, i) => {
      const [x, y] = transform(p[0], p[1]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw sector markers
    const sectorLength = points.length / 3;
    for (let i = 0; i < 3; i++) {
      const idx = Math.floor(i * sectorLength);
      if (idx < points.length) {
        const [x, y] = transform(points[idx][0], points[idx][1]);
        ctx.fillStyle = '#00ff88';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`S${i + 1}`, x, y - 25);
      }
    }

    // Draw start/finish line with checkered pattern
    if (points.length > 0) {
      const [x1, y1] = transform(points[0][0], points[0][1]);
      const lineLength = 40;
      const checkSize = 4;
      
      // Draw checkered pattern
      for (let i = 0; i < lineLength / checkSize; i++) {
        ctx.fillStyle = (i % 2 === 0) ? '#FFFFFF' : '#000000';
        ctx.fillRect(x1 - lineLength/2 + i * checkSize, y1 - checkSize/2, checkSize, checkSize);
      }
      
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.strokeRect(x1 - lineLength/2, y1 - checkSize/2, lineLength, checkSize);
    }
  }, []);

  const drawCarTrail = useCallback((ctx, car, transform) => {
    if (!carTrailsRef.current.has(car.name)) {
      carTrailsRef.current.set(car.name, []);
    }
    const trail = carTrailsRef.current.get(car.name);
    const [x, y] = transform(car.x, car.y);
    trail.push({ x, y, time: Date.now() });

    // Keep only last 20 points
    if (trail.length > 20) {
      trail.shift();
    }

    // Remove old points (> 2 seconds)
    const now = Date.now();
    while (trail.length > 0 && now - trail[0].time > 2000) {
      trail.shift();
    }

    // Draw trail
    if (trail.length > 1) {
      ctx.strokeStyle = car.color;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.3;
      ctx.beginPath();
      trail.forEach((point, idx) => {
        if (idx === 0) {
          ctx.moveTo(point.x, point.y);
        } else {
          ctx.lineTo(point.x, point.y);
        }
      });
      ctx.stroke();
      ctx.globalAlpha = 1.0;
    }
  }, []);

  const drawCar = useCallback((ctx, car, transform, isSelected) => {
    const [x, y] = transform(car.x, car.y);

    // Draw shadow
    ctx.save();
    ctx.translate(x + 2, y + 2);
    ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
    ctx.beginPath();
    ctx.ellipse(0, 0, 10, 6, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Draw speed trail with enhanced streaks for high speed
    if (car.speed > 50) {
      drawCarTrail(ctx, car, transform);
      
      // Enhanced speed streaks for very fast cars
      if (car.speed > 200) {
        const [x, y] = transform(car.x, car.y);
        const streakLength = (car.speed / 10) * 0.5;
        const streakGradient = ctx.createLinearGradient(
          x - Math.cos(car.angle) * streakLength,
          y - Math.sin(car.angle) * streakLength,
          x,
          y
        );
        streakGradient.addColorStop(0, 'transparent');
        streakGradient.addColorStop(0.5, `${car.color}80`);
        streakGradient.addColorStop(1, car.color);
        
        ctx.strokeStyle = streakGradient;
        ctx.lineWidth = 3;
        ctx.globalAlpha = 0.6;
        ctx.beginPath();
        ctx.moveTo(x - Math.cos(car.angle) * streakLength, y - Math.sin(car.angle) * streakLength);
        ctx.lineTo(x, y);
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      }
    }

    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(car.angle);

    // Car body with gradient
    const size = car.on_pit ? 8 : 14;
    const carGradient = ctx.createLinearGradient(-size, 0, size, 0);
    carGradient.addColorStop(0, car.color);
    carGradient.addColorStop(1, adjustBrightness(car.color, -20));
    
    ctx.fillStyle = carGradient;
    ctx.beginPath();
    ctx.moveTo(size, 0);
    ctx.lineTo(-size/2, -size/2);
    ctx.lineTo(-size/2, size/2);
    ctx.closePath();
    ctx.fill();

    // DRS indicator
    if (car.drs_active) {
      ctx.fillStyle = '#00ff00';
      ctx.beginPath();
      ctx.arc(size - 2, 0, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // White outline
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Highlight selected car
    if (isSelected) {
      ctx.strokeStyle = '#ffff00';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(0, 0, size + 5, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.restore();

    // Position label with background
    if (car.position !== undefined) {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(x - 15, y - 30, 30, 18);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`P${car.position}`, x, y - 18);
    }
    
    // Driver name (small)
    if (car.name) {
      ctx.fillStyle = car.color || '#ffffff';
      ctx.font = '10px sans-serif';
      ctx.fillText((car.name || '').substring(0, 6), x, y - 5);
    }
  }, [drawCarTrail]);

  const drawLidar = useCallback((ctx, car, transform) => {
    if (!car.lidar || !showLidar) return;

    const [x, y] = transform(car.x, car.y);
    const numRays = car.lidar.length;
    const maxRange = 10.0; // meters

    ctx.strokeStyle = 'rgba(0, 255, 255, 0.3)';
    ctx.lineWidth = 1;

    for (let i = 0; i < numRays; i += 4) { // Sample every 4th ray for performance
      const angle = (i / numRays) * Math.PI * 2 + car.angle;
      const distance = car.lidar[i] || maxRange;
      const endX = x + Math.cos(angle) * distance * 5; // Scale for visualization
      const endY = y + Math.sin(angle) * distance * 5;

      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(endX, endY);
      ctx.stroke();
    }
  }, [showLidar]);

  const adjustBrightness = (color, percent) => {
    const num = parseInt(color.replace("#", ""), 16);
    const r = Math.min(255, Math.max(0, (num >> 16) + percent));
    const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + percent));
    const b = Math.min(255, Math.max(0, (num & 0x0000FF) + percent));
    return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
  };

  const render = useCallback(() => {
    if (!trackData || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    const points = trackData.points;
    const xs = points.map(p => p[0]);
    const ys = points.map(p => p[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);

    const padding = 60;
    const baseScaleX = (width - 2 * padding) / (maxX - minX);
    const baseScaleY = (height - 2 * padding) / (maxY - minY);
    const baseScale = Math.min(baseScaleX, baseScaleY);
    const scale = baseScale * zoom;

    let centerX = (width - (maxX - minX) * scale) / 2 - minX * scale;
    let centerY = (height - (maxY - minY) * scale) / 2 - minY * scale;

    // Follow car mode
    if (followCar && interpolatedCars.length > 0) {
      const car = interpolatedCars.find(c => c.name === followCar);
      if (car) {
        centerX = width / 2 - car.x * scale;
        centerY = height / 2 - car.y * scale;
      }
    }

    // Apply pan
    centerX += pan.x;
    centerY += pan.y;

    const transform = (x, y) => {
      return [x * scale + centerX, y * scale + centerY];
    };

    // Draw track
    drawTrack(ctx, transform, points);

    // Draw tire marks
    const now = Date.now();
    tireMarkPositionsRef.current.forEach(mark => {
      if (now - mark.time < 5000) {
        const [x, y] = transform(mark.x, mark.y);
        const age = (now - mark.time) / 5000;
        ctx.strokeStyle = `${mark.color}${Math.floor((1 - age) * 100).toString(16).padStart(2, '0')}`;
        ctx.lineWidth = 2;
        ctx.globalAlpha = 1 - age;
        ctx.beginPath();
        // Draw skid marks
        for (let i = 0; i < 3; i++) {
          const offsetX = Math.cos(mark.angle + Math.PI / 2) * (i - 1) * 3;
          const offsetY = Math.sin(mark.angle + Math.PI / 2) * (i - 1) * 3;
          ctx.moveTo(x + offsetX, y + offsetY);
          ctx.lineTo(x + offsetX - Math.cos(mark.angle) * 10, y + offsetY - Math.sin(mark.angle) * 10);
        }
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      }
    });
    // Clean up old tire marks
    tireMarkPositionsRef.current = tireMarkPositionsRef.current.filter(
      mark => now - mark.time < 5000
    );

    // Draw cars
    if (interpolatedCars && interpolatedCars.length > 0) {
      // Sort by position for proper layering
      const sortedCars = [...interpolatedCars]
        .filter(car => car && car.x !== undefined && car.y !== undefined)
        .sort((a, b) => (a.position || 0) - (b.position || 0));
      
      sortedCars.forEach(car => {
        if (!car || car.x === undefined || car.y === undefined) return;
        const isSelected = followCar === car.name;
        drawCar(ctx, car, transform, isSelected);
        drawLidar(ctx, car, transform);
      });
    }

    animationFrameRef.current = requestAnimationFrame(render);
  }, [trackData, interpolatedCars, zoom, pan, followCar, drawTrack, drawCar, drawLidar]);

  useEffect(() => {
    render();
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [render]);

  const handleZoom = (delta) => {
    setZoom(prev => Math.max(0.5, Math.min(3.0, prev + delta)));
  };

  const handleMouseDown = (e) => {
    if (e.button === 0) { // Left click
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleCarClick = (carName) => {
    if (onCarClick) {
      onCarClick(carName);
    }
    setFollowCar(followCar === carName ? null : carName);
  };

  return (
    <div className="track-view-container">
      {/* Checkered Flag at top of track map */}
      <div 
        ref={checkeredFlagRef}
        className="track-checkered-flag"
      ></div>
      <div 
        ref={trackViewRef}
        className="track-view"
        onMouseDown={!is3DView ? handleMouseDown : undefined}
        onMouseMove={!is3DView ? handleMouseMove : undefined}
        onMouseUp={!is3DView ? handleMouseUp : undefined}
        onMouseLeave={!is3DView ? handleMouseUp : undefined}
      >
        <div ref={finishLineRef} className="finish-line-overlay"></div>
        
        <AnimatePresence mode="wait">
          {!is3DView ? (
            <motion.div
              key="2d-view"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.5 }}
              style={{ width: '100%', height: '100%' }}
            >
              <canvas 
                ref={canvasRef} 
                width={1200} 
                height={800}
                style={{ width: '100%', height: 'auto', cursor: isDragging ? 'grabbing' : 'grab' }}
                onClick={(e) => {
                  // Simple click detection for cars (would need more sophisticated hit testing)
                  const rect = canvasRef.current.getBoundingClientRect();
                  const x = e.clientX - rect.left;
                  const y = e.clientY - rect.top;
                  // This is simplified - would need proper hit testing
                }}
              />
            </motion.div>
          ) : (
            <motion.div
              key="3d-view"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.5 }}
              style={{ width: '100%', height: '800px' }}
            >
              <TrackView3D
                trackData={trackData}
                cars={interpolatedCars}
                followCar={followCar}
                onCarClick={handleCarClick}
              />
            </motion.div>
          )}
        </AnimatePresence>
        
        {/* Controls */}
        <div className="track-controls">
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => handleZoom(0.1)}
            className="control-btn"
            title="Zoom In"
          >
            <ZoomIn size={20} />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => handleZoom(-0.1)}
            className="control-btn"
            title="Zoom Out"
          >
            <ZoomOut size={20} />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => {
              setZoom(1.0);
              setPan({ x: 0, y: 0 });
              setFollowCar(null);
            }}
            className="control-btn"
            title="Reset View"
          >
            <Minimize2 size={20} />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setShowLidar(!showLidar)}
            className={`control-btn ${showLidar ? 'active' : ''}`}
            title="Toggle LiDAR"
          >
            <Maximize2 size={20} />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setIs3DView(!is3DView)}
            className={`control-btn ${is3DView ? 'active' : ''}`}
            title={is3DView ? "Switch to 2D View" : "Switch to 3D View"}
          >
            {is3DView ? <Square size={20} /> : <Box size={20} />}
          </motion.button>
        </div>

        {/* Mini-map */}
        {trackData && trackData.points && interpolatedCars && interpolatedCars.length > 0 && (
          <div className="minimap">
            <div className="minimap-title">Mini Map</div>
            <canvas
              width={200}
              height={150}
              style={{ width: '100%', height: 'auto', border: '1px solid #4a6fa5', borderRadius: '4px' }}
              ref={(ref) => {
                if (ref && trackData && trackData.points && trackData.points.length > 0) {
                  const ctx = ref.getContext('2d');
                  const xs = trackData.points.map(p => p[0]);
                  const ys = trackData.points.map(p => p[1]);
                  const minX = Math.min(...xs);
                  const maxX = Math.max(...xs);
                  const minY = Math.min(...ys);
                  const maxY = Math.max(...ys);
                  
                  const scaleX = 200 / Math.max(maxX - minX, 1);
                  const scaleY = 150 / Math.max(maxY - minY, 1);
                  const scale = Math.min(scaleX, scaleY);
                  
                  ctx.clearRect(0, 0, 200, 150);
                  ctx.strokeStyle = '#4a6fa5';
                  ctx.lineWidth = 2;
                  ctx.beginPath();
                  trackData.points.forEach((p, i) => {
                    const x = (p[0] - minX) * scale;
                    const y = (p[1] - minY) * scale;
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                  });
                  ctx.closePath();
                  ctx.stroke();

                  // Draw cars on minimap
                  interpolatedCars
                    .filter(car => car && car.x !== undefined && car.y !== undefined)
                    .forEach(car => {
                      const x = (car.x - minX) * scale;
                      const y = (car.y - minY) * scale;
                      ctx.fillStyle = car.color || '#ffffff';
                      ctx.beginPath();
                      ctx.arc(x, y, 2, 0, Math.PI * 2);
                      ctx.fill();
                    });
                }
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default TrackView;
