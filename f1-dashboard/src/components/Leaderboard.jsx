import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Gauge, Zap, TrendingUp, ChevronDown, ChevronUp } from 'lucide-react';
import { positionChange, drsPulse, overtakingBadge, lapCounterFlip } from '../utils/animations';
import './Leaderboard.css';

const Leaderboard = ({ cars = [], raceTime = 0, totalLaps = 15, onCarClick }) => {
  const [sortedCars, setSortedCars] = useState([]);
  const [prevPositions, setPrevPositions] = useState({});
  const [showAll, setShowAll] = useState(false);
  const rowRefs = useRef({});
  const drsRefs = useRef({});
  const overtakingRefs = useRef({});
  const lapCounterRef = useRef(null);
  const prevLapRef = useRef(0);
  const leaderboardRef = useRef(null);
  const animationTimeoutRef = useRef(null);
  const pendingAnimationsRef = useRef(new Map());

  useEffect(() => {
    if (!cars || cars.length === 0) {
      setSortedCars([]);
      return;
    }
    const newSorted = [...cars].sort((a, b) => (a.position || 0) - (b.position || 0));
    
    // Detect position changes for animations
    const oldPositions = { ...prevPositions };
    const newPositions = {};
    const positionChanges = [];
    
    newSorted.forEach(car => {
      newPositions[car.name] = car.position;
      
      // Collect position changes instead of animating immediately
      if (oldPositions[car.name] && oldPositions[car.name] !== car.position) {
        positionChanges.push({
          carName: car.name,
          oldPosition: oldPositions[car.name],
          newPosition: car.position,
          direction: oldPositions[car.name] > car.position ? 'up' : 'down'
        });
      }
    });
    
    // Update positions and sorted cars immediately for layout animation
    setPrevPositions(newPositions);
    setSortedCars(newSorted);
    
    // Throttle position change animations to prevent vibration
    if (positionChanges.length > 0) {
      // Clear any pending timeout
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
      
      // Store pending animations (overwrite if same car changes again)
      positionChanges.forEach(change => {
        pendingAnimationsRef.current.set(change.carName, change);
      });
      
      // Debounce: wait 200ms before animating to batch rapid changes
      // This prevents vibration when positions change rapidly
      animationTimeoutRef.current = setTimeout(() => {
        // Only animate the final position change for each car
        pendingAnimationsRef.current.forEach((change, carName) => {
          const rowElement = rowRefs.current[carName];
          if (rowElement) {
            // Use the latest direction based on final position
            const finalDirection = change.oldPosition > change.newPosition ? 'up' : 'down';
            positionChange(rowElement, finalDirection, { duration: 500, intensity: 0.6 });
          }
        });
        pendingAnimationsRef.current.clear();
      }, 200);
    }
    
    // Cleanup on unmount
    return () => {
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
    };
  }, [cars]);

  // Animate DRS indicators
  useEffect(() => {
    sortedCars.forEach(car => {
      if (car.drs_active && drsRefs.current[car.name]) {
        drsPulse(drsRefs.current[car.name], { 
          duration: 1000,
          color: '#00ff00',
          intensity: 1
        });
      }
    });
  }, [sortedCars]);

  // Animate overtaking badges
  useEffect(() => {
    sortedCars.forEach(car => {
      if (car.overtaking && overtakingRefs.current[car.name]) {
        overtakingBadge(overtakingRefs.current[car.name], { duration: 800 });
      }
    });
  }, [sortedCars]);

  // Lap counter flip animation
  useEffect(() => {
    const currentLap = cars && cars.length > 0 ? Math.max(...cars.map(c => c.laps || 0)) : 0;
    if (currentLap > prevLapRef.current && lapCounterRef.current) {
      lapCounterFlip(lapCounterRef.current, currentLap, { duration: 500 });
    }
    prevLapRef.current = currentLap;
  }, [cars]);

  const getTyreColor = (tyre) => {
    const colors = {
      'SOFT': '#ff0000',
      'MEDIUM': '#ffff00',
      'HARD': '#ffffff',
      'INTERMEDIATE': '#00aaff',
      'WET': '#00ff00'
    };
    return colors[tyre] || '#999';
  };

  const getTireTempColor = (temp) => {
    if (temp < 80) return '#4a90e2'; // Cold - blue
    if (temp < 100) return '#44ff44'; // Optimal - green
    if (temp < 120) return '#ffaa00'; // Warm - orange
    return '#ff4444'; // Hot - red
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(1);
    return `${mins}:${secs.padStart(4, '0')}`;
  };

  const getPodiumClass = (position) => {
    if (position === 1) return 'podium-gold';
    if (position === 2) return 'podium-silver';
    if (position === 3) return 'podium-bronze';
    return '';
  };

  const calculateGapToLeader = (car, leader) => {
    if (!leader || car.position === 1) return '--';
    // Use time_interval if available, otherwise calculate from total_time
    const gap = car.time_interval !== undefined ? car.time_interval.toFixed(1) : (car.total_time - leader.total_time).toFixed(1);
    return `+${gap}s`;
  };

  const leader = sortedCars.find(c => c.position === 1);

  return (
    <div className="leaderboard" ref={leaderboardRef}>
      <div className="leaderboard-header">
        <motion.h2
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          RACE CLASSIFICATION
        </motion.h2>
        <div className="race-info">
          <motion.span 
            className="race-time"
            key={raceTime}
            initial={{ scale: 1.2 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.3 }}
          >
            ⏱️ {formatTime(raceTime)}
          </motion.span>
          <span className="lap-counter">
            🏁 Lap <span ref={lapCounterRef}>{cars && cars.length > 0 ? Math.max(...cars.map(c => c.laps || 0)) : 0}</span> / {totalLaps}
          </span>
        </div>
      </div>
      
      <div className="leaderboard-table">
        <div className="table-header">
          <span className="col-pos">Pos</span>
          <span className="col-driver">Driver</span>
          <span className="col-gap">Gap</span>
          <span className="col-speed">Speed</span>
          <span className="col-rpm">Wear</span>
          <span className="col-gear">G</span>
          <span className="col-tyre">Tyre</span>
          <span className="col-temp">Temp</span>
          <span className="col-drs">DRS</span>
        </div>
        
        <AnimatePresence>
          {(showAll ? sortedCars : sortedCars.slice(0, 5)).map((car, index) => {
            const prevPos = prevPositions[car.name] || car.position;
            const positionChange = prevPos - car.position;
            
            return (
              <motion.div
                key={car.name}
                ref={(el) => { if (el) rowRefs.current[car.name] = el; }}
                initial={{ opacity: 0, x: positionChange > 0 ? -50 : positionChange < 0 ? 50 : 0 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, transition: { duration: 0.2 } }}
                transition={{ 
                  opacity: { duration: 0.3, ease: [0.4, 0, 0.2, 1] },
                  x: { duration: 0.4, ease: [0.4, 0, 0.2, 1] },
                  delay: index * 0.03,
                  layout: { 
                    type: "spring",
                    stiffness: 300,
                    damping: 30,
                    mass: 0.8
                  }
                }}
                layout
                className={`table-row ${car.on_pit ? 'in-pit' : ''} ${getPodiumClass(car.position)}`}
                style={{ borderLeft: `4px solid ${car.color}` }}
                onClick={() => onCarClick && onCarClick(car.name)}
              >
                <motion.span 
                  className="col-pos position-badge"
                  animate={{ scale: positionChange !== 0 ? 1.15 : 1 }}
                  transition={{ 
                    type: "spring",
                    stiffness: 400,
                    damping: 25,
                    mass: 0.6
                  }}
                >
                  {car.position}
                  {positionChange > 0 && <span className="position-up">↑</span>}
                  {positionChange < 0 && <span className="position-down">↓</span>}
                </motion.span>
                
                <span className="col-driver">
                  <span className="driver-color" style={{ backgroundColor: car.color }}></span>
                  <span className="driver-name">{car.name}</span>
                  {car.overtaking && (
                    <span 
                      ref={(el) => { if (el) overtakingRefs.current[car.name] = el; }}
                      className="overtaking-badge"
                    >
                      OVT
                    </span>
                  )}
                </span>
                
                <span className="col-gap">
                  {calculateGapToLeader(car, leader)}
                </span>
                
                <span className="col-speed">
                  <div className="speed-value">{Math.round(car.speed || 0)}</div>
                  <div className="speed-unit">km/h</div>
                </span>
                
                <span className="col-rpm">
                  <div className="rpm-gauge">
                    <Gauge size={16} />
                    <span className="rpm-value">{Math.round((car.wear || 0) * 100)}%</span>
                  </div>
                </span>
                
                <span className="col-gear">
                  <div className={`gear-badge gear-${car.gear || 1}`}>
                    {car.gear || 1}
                  </div>
                </span>
                
                <span className="col-tyre">
                  <span 
                    className="tyre-indicator" 
                    style={{ backgroundColor: getTyreColor(car.tyre) }}
                  ></span>
                  <span className="tyre-text">{car.tyre}</span>
                  <div className="wear-indicator">
                    <div 
                      className="wear-fill-mini" 
                      style={{ 
                        width: `${(car.wear || 0) * 100}%`,
                        backgroundColor: car.wear > 0.7 ? '#ff4444' : car.wear > 0.4 ? '#ffaa00' : '#44ff44'
                      }}
                    ></div>
                  </div>
                  <span className="wear-percentage">{Math.round((car.wear || 0) * 100)}%</span>
                </span>
                
                <span className="col-temp">
                  <div 
                    className="temp-indicator"
                    style={{ color: getTireTempColor(car.tire_temp || 100) }}
                  >
                    {Math.round(car.tire_temp || 100)}°C
                  </div>
                </span>
                
                <span className="col-drs">
                  {car.drs_active ? (
                    <div
                      ref={(el) => { if (el) drsRefs.current[car.name] = el; }}
                      className="drs-active"
                    >
                      <Zap size={14} />
                    </div>
                  ) : (
                    <div className="drs-inactive">--</div>
                  )}
                </span>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
      
      {sortedCars.length > 5 && (
        <button 
          className="show-more-leaderboard"
          onClick={() => setShowAll(!showAll)}
        >
          {showAll ? (
            <>
              <ChevronUp size={14} />
              Show Less
            </>
          ) : (
            <>
              <ChevronDown size={14} />
              Show All ({sortedCars.length - 5} more)
            </>
          )}
        </button>
      )}
      
      {sortedCars && sortedCars.length > 0 && sortedCars.some(car => car.on_pit) && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="pit-alert"
        >
          🔧 {sortedCars.filter(car => car.on_pit).map(car => car.name).join(', ')} in PIT
        </motion.div>
      )}
    </div>
  );
};

export default Leaderboard;
