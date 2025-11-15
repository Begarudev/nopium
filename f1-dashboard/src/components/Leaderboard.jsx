import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Gauge, Zap, TrendingUp } from 'lucide-react';
import './Leaderboard.css';

const Leaderboard = ({ cars = [], raceTime = 0, totalLaps = 15, onCarClick }) => {
  const [sortedCars, setSortedCars] = useState([]);
  const [prevPositions, setPrevPositions] = useState({});

  useEffect(() => {
    if (!cars || cars.length === 0) {
      setSortedCars([]);
      return;
    }
    const newSorted = [...cars].sort((a, b) => (a.position || 0) - (b.position || 0));
    
    // Detect position changes for animations
    const newPositions = {};
    newSorted.forEach(car => {
      newPositions[car.name] = car.position;
    });
    setPrevPositions(newPositions);
    setSortedCars(newSorted);
  }, [cars]);

  const getTyreColor = (tyre) => {
    const colors = {
      'SOFT': '#ff0000',
      'MEDIUM': '#ffff00',
      'HARD': '#ffffff',
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
    const gap = (car.total_time - leader.total_time).toFixed(1);
    return `+${gap}s`;
  };

  const leader = sortedCars.find(c => c.position === 1);

  return (
    <div className="leaderboard">
      <div className="leaderboard-header">
        <motion.h2
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          Race Leaderboard
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
            🏁 Lap {cars && cars.length > 0 ? Math.max(...cars.map(c => c.laps || 0)) : 0} / {totalLaps}
          </span>
        </div>
      </div>
      
      <div className="leaderboard-table">
        <div className="table-header">
          <span className="col-pos">Pos</span>
          <span className="col-driver">Driver</span>
          <span className="col-gap">Gap</span>
          <span className="col-speed">Speed</span>
          <span className="col-rpm">RPM</span>
          <span className="col-gear">G</span>
          <span className="col-tyre">Tyre</span>
          <span className="col-temp">Temp</span>
          <span className="col-drs">DRS</span>
        </div>
        
        <AnimatePresence>
          {sortedCars.map((car, index) => {
            const prevPos = prevPositions[car.name] || car.position;
            const positionChange = prevPos - car.position;
            
            return (
              <motion.div
                key={car.name}
                initial={{ opacity: 0, x: positionChange > 0 ? -50 : positionChange < 0 ? 50 : 0 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, delay: index * 0.05 }}
                layout
                className={`table-row ${car.on_pit ? 'in-pit' : ''} ${getPodiumClass(car.position)}`}
                style={{ borderLeft: `4px solid ${car.color}` }}
                onClick={() => onCarClick && onCarClick(car.name)}
              >
                <motion.span 
                  className="col-pos position-badge"
                  animate={{ scale: positionChange !== 0 ? 1.2 : 1 }}
                  transition={{ duration: 0.3 }}
                >
                  {car.position}
                  {positionChange > 0 && <span className="position-up">↑</span>}
                  {positionChange < 0 && <span className="position-down">↓</span>}
                </motion.span>
                
                <span className="col-driver">
                  <span className="driver-color" style={{ backgroundColor: car.color }}></span>
                  <span className="driver-name">{car.name}</span>
                  {car.overtaking && <span className="overtaking-badge">OVT</span>}
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
                    <span className="rpm-value">{Math.round(car.rpm || 0)}</span>
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
                    <motion.div
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ repeat: Infinity, duration: 1 }}
                      className="drs-active"
                    >
                      <Zap size={14} />
                    </motion.div>
                  ) : (
                    <div className="drs-inactive">--</div>
                  )}
                </span>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
      
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
