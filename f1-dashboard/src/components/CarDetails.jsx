import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Gauge, Zap, Thermometer, Droplet } from 'lucide-react';
import './CarDetails.css';

const CarDetails = ({ car, isOpen, onClose, containerRef }) => {
  const modalRef = useRef(null);
  const [position, setPosition] = useState({ top: '50%', left: '50%' });
  const [overlayStyle, setOverlayStyle] = useState({});

  useEffect(() => {
    const updatePosition = () => {
      if (containerRef?.current && isOpen) {
        const rect = containerRef.current.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
        
        // Calculate visible portion of the right column
        const viewportTop = Math.max(0, rect.top);
        const viewportBottom = Math.min(window.innerHeight, rect.bottom);
        const visibleTop = Math.max(rect.top, 0);
        const visibleHeight = Math.max(0, viewportBottom - viewportTop);
        
        // Center in the visible viewport of the right column
        const centerX = rect.left + rect.width / 2 + scrollLeft;
        const centerY = visibleTop + visibleHeight / 2 + scrollTop;
        
        setPosition({
          top: `${centerY}px`,
          left: `${centerX}px`
        });

        // Update overlay to cover only the right column visible area
        setOverlayStyle({
          top: `${visibleTop + scrollTop}px`,
          left: `${rect.left + scrollLeft}px`,
          width: `${rect.width}px`,
          height: `${visibleHeight}px`,
        });
      }
    };

    if (isOpen) {
      updatePosition();
      window.addEventListener('resize', updatePosition);
      window.addEventListener('scroll', updatePosition, true);
      
      return () => {
        window.removeEventListener('resize', updatePosition);
        window.removeEventListener('scroll', updatePosition, true);
      };
    }
  }, [isOpen, containerRef]);

  if (!car) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            className="car-details-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={overlayStyle}
          />
          <motion.div
            className="car-details-modal-wrapper"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.3 }}
            transformTemplate={({ scale }) => `translate(-50%, -50%) scale(${scale})`}
            style={position}
          >
            <div
              ref={modalRef}
              className="car-details-modal"
            >
            <div className="car-details-header">
              <div className="car-details-title">
                <div className="car-color-indicator" style={{ backgroundColor: car.color }}></div>
                <h2>{car.name}</h2>
                <span className="position-badge-large">P{car.position}</span>
              </div>
              <button className="close-button" onClick={onClose}>
                <X size={20} />
              </button>
            </div>

            <div className="car-details-content">
              {/* Performance Metrics */}
              <div className="details-section">
                <h3>Performance</h3>
                <div className="metrics-grid">
                  <div className="metric-item">
                    <Gauge size={20} />
                    <div className="metric-content">
                      <div className="metric-label">Speed</div>
                      <div className="metric-value">{Math.round(car.speed || 0)} km/h</div>
                    </div>
                  </div>
                  <div className="metric-item">
                    <Zap size={20} />
                    <div className="metric-content">
                      <div className="metric-label">Tyre Wear</div>
                      <div className="metric-value">{Math.round((car.wear || 0) * 100)}%</div>
                      <div className="metric-bar">
                        <div 
                          className="metric-bar-fill"
                          style={{ 
                            width: `${(car.wear || 0) * 100}%`,
                            backgroundColor: car.wear > 0.7 ? '#ff4444' : car.wear > 0.4 ? '#ffaa00' : '#44ff44'
                          }}
                        ></div>
                      </div>
                    </div>
                  </div>
                  <div className="metric-item">
                    <div className="metric-content">
                      <div className="metric-label">Gear</div>
                      <div className="metric-value-large">{car.gear || 1}</div>
                    </div>
                  </div>
                  <div className="metric-item">
                    <div className="metric-content">
                      <div className="metric-label">Throttle</div>
                      <div className="metric-value">{Math.round((car.throttle || 0) * 100)}%</div>
                      <div className="metric-bar">
                        <div 
                          className="metric-bar-fill throttle-bar"
                          style={{ width: `${(car.throttle || 0) * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  </div>
                  <div className="metric-item">
                    <div className="metric-content">
                      <div className="metric-label">Brake</div>
                      <div className="metric-value">{Math.round((car.brake || 0) * 100)}%</div>
                      <div className="metric-bar">
                        <div 
                          className="metric-bar-fill brake-bar"
                          style={{ width: `${(car.brake || 0) * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Tire Information */}
              <div className="details-section">
                <h3>Tire Information</h3>
                <div className="tire-info">
                  <div className="tire-item">
                    <div className="tire-label">Compound</div>
                    <div className="tire-value">{car.tyre}</div>
                    <div 
                      className="tire-color-indicator"
                      style={{ 
                        backgroundColor: car.tyre === 'SOFT' ? '#ff0000' : 
                                       car.tyre === 'MEDIUM' ? '#ffff00' : 
                                       car.tyre === 'HARD' ? '#ffffff' :
                                       car.tyre === 'INTERMEDIATE' ? '#00aaff' :
                                       car.tyre === 'WET' ? '#00ff00' : '#999999'
                      }}
                    ></div>
                  </div>
                  <div className="tire-item">
                    <Thermometer size={18} />
                    <div className="tire-content">
                      <div className="tire-label">Temperature</div>
                      <div className="tire-value">{Math.round(car.tire_temp || 100)}°C</div>
                    </div>
                  </div>
                  <div className="tire-item">
                    <div className="tire-content">
                      <div className="tire-label">Wear</div>
                      <div className="tire-value">{(car.wear || 0) * 100}%</div>
                      <div className="wear-bar-large">
                        <div 
                          className="wear-fill-large"
                          style={{ 
                            width: `${(car.wear || 0) * 100}%`,
                            backgroundColor: car.wear > 0.7 ? '#ff4444' : car.wear > 0.4 ? '#ffaa00' : '#44ff44'
                          }}
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Car Status */}
              <div className="details-section">
                <h3>Status</h3>
                <div className="status-grid">
                  <div className="status-item-detailed">
                    <span className="status-label">DRS</span>
                    <span className={`status-badge ${car.drs_active ? 'active' : 'inactive'}`}>
                      {car.drs_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </div>
                  <div className="status-item-detailed">
                    <span className="status-label">Controller</span>
                    <span className="status-badge">{car.controller_type || 'N/A'}</span>
                  </div>
                  <div className="status-item-detailed">
                    <span className="status-label">Overtaking</span>
                    <span className={`status-badge ${car.overtaking ? 'active' : 'inactive'}`}>
                      {car.overtaking ? 'YES' : 'NO'}
                    </span>
                  </div>
                  <div className="status-item-detailed">
                    <Droplet size={18} />
                    <span className="status-label">Fuel</span>
                    <span className="status-badge">{Math.round(car.fuel || 0)}%</span>
                  </div>
                </div>
              </div>

              {/* Race Information */}
              <div className="details-section">
                <h3>Race Info</h3>
                <div className="race-info-grid">
                  <div className="info-item">
                    <span className="info-label">Laps</span>
                    <span className="info-value">{car.laps || 0}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Total Time</span>
                    <span className="info-value">{(car.total_time || 0).toFixed(1)}s</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">On Pit</span>
                    <span className={`info-value ${car.on_pit ? 'pit-active' : ''}`}>
                      {car.on_pit ? 'YES' : 'NO'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Pitstop History */}
              <div className="details-section">
                <h3>Pitstop History</h3>
                <div className="pitstop-info">
                  <div className="pitstop-count">
                    <span className="info-label">Total Pitstops:</span>
                    <span className="info-value">{car.pitstop_count || 0}</span>
                  </div>
                  {car.pitstop_history && car.pitstop_history.length > 0 && (
                    <div className="pitstop-list">
                      {car.pitstop_history.map((pitstop, index) => (
                        <div key={index} className="pitstop-item">
                          <span className="pitstop-lap">Lap {pitstop.lap}</span>
                          <span className="pitstop-tyres">
                            {pitstop.tyre} → {pitstop.new_tyre || 'N/A'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {(!car.pitstop_history || car.pitstop_history.length === 0) && (
                    <div className="no-pitstops">No pitstops yet</div>
                  )}
                </div>
              </div>
            </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default CarDetails;

