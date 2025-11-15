import React from 'react';
import { motion } from 'framer-motion';
import { CloudRain, Thermometer, Wind, Droplets } from 'lucide-react';
import './WeatherPanel.css';

const WeatherPanel = ({ weather = { rain: 0, track_temp: 25, wind: 0 }, tyreDistribution = {} }) => {
  const getRainLevel = (rain) => {
    if (rain < 0.1) return 'Dry';
    if (rain < 0.3) return 'Light Rain';
    if (rain < 0.6) return 'Heavy Rain';
    return 'Storm';
  };

  const getRainColor = (rain) => {
    if (rain < 0.1) return '#00ff88';
    if (rain < 0.3) return '#4a90e2';
    if (rain < 0.6) return '#ffaa00';
    return '#ff4444';
  };

  const getTyreColor = (tyre) => {
    const colors = {
      'SOFT': '#ff0000',
      'MEDIUM': '#ffff00',
      'HARD': '#ffffff',
      'WET': '#00ff00'
    };
    return colors[tyre] || '#999';
  };

  const getTyreRecommendation = (rain, trackTemp) => {
    if (rain > 0.3) return 'WET';
    if (trackTemp > 35) return 'SOFT';
    if (trackTemp < 20) return 'HARD';
    return 'MEDIUM';
  };

  const recommendation = getTyreRecommendation(weather.rain, weather.track_temp);

  return (
    <motion.div
      className="weather-panel"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="weather-section">
        <h3>Weather Conditions</h3>
        <div className="weather-grid">
          <motion.div
            className="weather-item"
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.2 }}
          >
            <CloudRain 
              size={24} 
              style={{ color: getRainColor(weather.rain) }}
            />
            <div className="weather-details">
              <span className="weather-label">Conditions</span>
              <span 
                className="weather-value"
                style={{ color: getRainColor(weather.rain) }}
              >
                {getRainLevel(weather.rain)}
              </span>
            </div>
          </motion.div>

          <motion.div
            className="weather-item"
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.2 }}
          >
            <Thermometer size={24} />
            <div className="weather-details">
              <span className="weather-label">Track Temp</span>
              <span className="weather-value">
                {weather.track_temp.toFixed(1)}°C
              </span>
            </div>
            <div className="temp-bar">
              <div 
                className="temp-fill"
                style={{ 
                  width: `${(weather.track_temp / 50) * 100}%`,
                  backgroundColor: weather.track_temp > 35 ? '#ff4444' : 
                                 weather.track_temp > 25 ? '#ffaa00' : '#4a90e2'
                }}
              ></div>
            </div>
          </motion.div>

          <motion.div
            className="weather-item"
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.2 }}
          >
            <Wind size={24} />
            <div className="weather-details">
              <span className="weather-label">Wind</span>
              <span className="weather-value">
                {weather.wind.toFixed(1)} m/s
              </span>
            </div>
          </motion.div>

          <motion.div
            className="weather-item"
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.2 }}
          >
            <Droplets 
              size={24}
              style={{ color: getRainColor(weather.rain) }}
            />
            <div className="weather-details">
              <span className="weather-label">Rain Level</span>
              <span 
                className="weather-value"
                style={{ color: getRainColor(weather.rain) }}
              >
                {(weather.rain * 100).toFixed(0)}%
              </span>
            </div>
            <div className="rain-bar">
              <div 
                className="rain-fill"
                style={{ 
                  width: `${weather.rain * 100}%`,
                  backgroundColor: getRainColor(weather.rain)
                }}
              ></div>
            </div>
          </motion.div>
        </div>

        {/* Visual rain effect */}
        {weather.rain > 0.1 && (
          <motion.div
            className="rain-effect"
            initial={{ opacity: 0 }}
            animate={{ opacity: weather.rain }}
            transition={{ duration: 1 }}
          >
            {Array.from({ length: 20 }).map((_, i) => (
              <motion.div
                key={i}
                className="rain-drop"
                style={{
                  left: `${(i * 5)}%`,
                  animationDelay: `${i * 0.1}s`
                }}
                animate={{
                  y: [0, 100],
                  opacity: [0.5, 0]
                }}
                transition={{
                  duration: 1,
                  repeat: Infinity,
                  delay: i * 0.1
                }}
              />
            ))}
          </motion.div>
        )}
      </div>

      <div className="tyre-section">
        <h3>Tyre Distribution</h3>
        <div className="tyre-grid">
          {Object.entries(tyreDistribution || {}).map(([tyre, count]) => (
            <motion.div
              key={tyre}
              className={`tyre-item ${tyre === recommendation ? 'recommended' : ''}`}
              whileHover={{ scale: 1.1 }}
              transition={{ duration: 0.2 }}
            >
              <div 
                className="tyre-indicator-large"
                style={{ backgroundColor: getTyreColor(tyre) }}
              ></div>
              <span className="tyre-name">{tyre}</span>
              <span className="tyre-count">{count} cars</span>
              {tyre === recommendation && (
                <span className="recommendation-badge">Recommended</span>
              )}
            </motion.div>
          ))}
        </div>
        <div className="tyre-recommendation">
          <span className="recommendation-label">Strategy:</span>
          <span 
            className="recommendation-value"
            style={{ color: getTyreColor(recommendation) }}
          >
            {recommendation} compound recommended
          </span>
        </div>
      </div>
    </motion.div>
  );
};

export default WeatherPanel;
