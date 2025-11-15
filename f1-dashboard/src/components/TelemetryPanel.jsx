import React, { useState, useEffect, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { motion } from 'framer-motion';
import { Gauge as GaugeIcon, Zap } from 'lucide-react';
import { speedometerSweep, gearShift, telemetryFlow, animatedCounter } from '../utils/animations';
import './TelemetryPanel.css';

const TelemetryPanel = ({ selectedCar, cars = [] }) => {
  const [telemetryData, setTelemetryData] = useState([]);
  const maxDataPoints = 50;
  const timeRef = useRef(0);
  const speedValueRef = useRef(null);
  const wearValueRef = useRef(null);
  const gearDisplayRef = useRef(null);
  const chartContainerRef = useRef(null);
  const prevGearRef = useRef(null);
  const prevSpeedRef = useRef(0);
  const prevWearRef = useRef(0);

  useEffect(() => {
    if (!selectedCar) return;
    
    const car = cars.find(c => c.name === selectedCar);
    if (!car) return;

    const newPoint = {
      time: timeRef.current++,
      speed: car.speed || 0,
      throttle: (car.throttle || 0) * 100,
      brake: (car.brake || 0) * 100,
      wear: (car.wear || 0) * 100
    };

    setTelemetryData(prev => {
      const updated = [...prev, newPoint];
      return updated.slice(-maxDataPoints);
    });

    // Animate speedometer sweep
    if (speedValueRef.current && car.speed !== prevSpeedRef.current) {
      speedometerSweep(speedValueRef.current, car.speed || 0, {
        duration: 800,
        min: 0,
        max: 350
      });
      prevSpeedRef.current = car.speed || 0;
    }

    // Animate wear counter
    if (wearValueRef.current && car.wear !== undefined) {
      const wearPercent = (car.wear || 0) * 100;
      if (Math.abs(wearPercent - prevWearRef.current) > 1) {
        animatedCounter(wearValueRef.current, wearPercent, {
          duration: 600,
          decimals: 0
        });
        prevWearRef.current = wearPercent;
      }
    }

    // Animate gear shift
    if (gearDisplayRef.current && car.gear !== prevGearRef.current) {
      gearShift(gearDisplayRef.current, car.gear || 1, { duration: 400 });
      prevGearRef.current = car.gear || 1;
    }
  }, [selectedCar, cars]);

  // Telemetry flow animation
  useEffect(() => {
    if (chartContainerRef.current && selectedCar) {
      const flowInterval = setInterval(() => {
        telemetryFlow(chartContainerRef.current, {
          duration: 2000,
          color: '#4a90e2',
          direction: 'right'
        });
      }, 3000);
      return () => clearInterval(flowInterval);
    }
  }, [selectedCar]);

  if (!selectedCar) {
    return (
      <div className="telemetry-panel">
        <div className="telemetry-placeholder">
          <p>Select a car to view telemetry</p>
        </div>
      </div>
    );
  }

  const car = cars.find(c => c.name === selectedCar);
  if (!car) return null;

  const wearPercentage = (car.wear || 0) * 100;
  const speedPercentage = ((car.speed || 0) / 350) * 100;

  return (
    <motion.div
      className="telemetry-panel"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="telemetry-header">
        <h3>{car.name} - Telemetry</h3>
        <div className="car-indicator" style={{ backgroundColor: car.color }}></div>
      </div>

      <div className="telemetry-content">
        {/* Gauges */}
        <div className="gauges-row">
          <div className="gauge-container">
            <div className="gauge-label">Tyre Wear</div>
            <div className="gauge-wrapper">
              <ResponsiveContainer width="100%" height={120}>
                <LineChart data={[{ value: wearPercentage }]}>
                  <Line 
                    type="monotone" 
                    dataKey="value" 
                    stroke={wearPercentage > 70 ? '#ff4444' : wearPercentage > 40 ? '#ffaa00' : '#44ff44'} 
                    strokeWidth={3}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
              <div className="gauge-value" ref={wearValueRef}>{Math.round(wearPercentage)}</div>
              <div className="gauge-unit">%</div>
            </div>
          </div>

          <div className="gauge-container">
            <div className="gauge-label">Speed</div>
            <div className="gauge-wrapper">
              <div className="speedometer">
                <svg className="speedometer-svg" viewBox="0 0 200 120">
                  {/* Gauge arc background */}
                  <path
                    d="M 20 100 A 80 80 0 0 1 180 100"
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  {/* Gauge arc active (colored based on speed) */}
                  <path
                    className="speedometer-arc"
                    d="M 20 100 A 80 80 0 0 1 180 100"
                    fill="none"
                    stroke="#4a90e2"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={`${(speedPercentage / 100) * 251.2} 251.2`}
                    transform="rotate(180 100 100)"
                    style={{ transformOrigin: '100px 100px' }}
                  />
                  {/* Tick marks */}
                  {[0, 50, 100, 150, 200, 250, 300, 350].map((value, index) => {
                    const angle = 180 - (value / 350) * 180;
                    const radian = (angle * Math.PI) / 180;
                    const x1 = 100 + 70 * Math.cos(radian);
                    const y1 = 100 - 70 * Math.sin(radian);
                    const x2 = 100 + 80 * Math.cos(radian);
                    const y2 = 100 - 80 * Math.sin(radian);
                    return (
                      <line
                        key={index}
                        x1={x1}
                        y1={y1}
                        x2={x2}
                        y2={y2}
                        stroke="rgba(255, 255, 255, 0.4)"
                        strokeWidth="2"
                      />
                    );
                  })}
                  {/* Needle */}
                  <g className="speedometer-needle">
                    <line
                      x1="100"
                      y1="100"
                      x2={100 + 60 * Math.cos(((180 - (speedPercentage / 100) * 180) * Math.PI) / 180)}
                      y2={100 - 60 * Math.sin(((180 - (speedPercentage / 100) * 180) * Math.PI) / 180)}
                      stroke="#E10600"
                      strokeWidth="3"
                      strokeLinecap="round"
                      style={{
                        transformOrigin: '100px 100px',
                        transition: 'transform 0.3s ease-out'
                      }}
                    />
                    {/* Needle center dot */}
                    <circle cx="100" cy="100" r="4" fill="#E10600" />
                  </g>
                </svg>
                <div className="speedometer-value" ref={speedValueRef}>
                  {Math.round(car.speed || 0)}
                </div>
                <div className="speedometer-unit">km/h</div>
              </div>
            </div>
          </div>

          <div className="gauge-container">
            <div className="gauge-label">Gear</div>
            <div className="gear-display">
              <div 
                ref={gearDisplayRef}
                className={`gear-number gear-${car.gear || 1}`}
              >
                {car.gear || 1}
              </div>
            </div>
          </div>
        </div>

        {/* Charts */}
        <div className="charts-row" ref={chartContainerRef}>
          <div className="chart-container">
            <div className="chart-title">Speed vs Time</div>
            <ResponsiveContainer width="100%" height={150}>
              <LineChart data={telemetryData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3f5f" />
                <XAxis dataKey="time" stroke="#888" />
                <YAxis stroke="#888" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1a1f3a', border: '1px solid #4a6fa5' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="speed" 
                  stroke="#4a90e2" 
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-container">
            <div className="chart-title">Tyre Wear vs Time</div>
            <ResponsiveContainer width="100%" height={150}>
              <LineChart data={telemetryData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3f5f" />
                <XAxis dataKey="time" stroke="#888" />
                <YAxis stroke="#888" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1a1f3a', border: '1px solid #4a6fa5' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="wear" 
                  stroke="#ff4444" 
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Status indicators */}
        <div className="status-row">
          <div className="status-item">
            <span className="status-label">DRS:</span>
            <span className={`status-value ${car.drs_active ? 'active' : 'inactive'}`}>
              {car.drs_active ? 'ACTIVE' : 'INACTIVE'}
            </span>
          </div>
          <div className="status-item">
            <span className="status-label">Controller:</span>
            <span className="status-value">{car.controller_type || 'N/A'}</span>
          </div>
          <div className="status-item">
            <span className="status-label">Overtaking:</span>
            <span className={`status-value ${car.overtaking ? 'active' : 'inactive'}`}>
              {car.overtaking ? 'YES' : 'NO'}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default TelemetryPanel;

