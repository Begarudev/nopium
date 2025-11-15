import React from 'react';
import { motion } from 'framer-motion';
import { CloudRain, Thermometer, Wind, Droplets } from 'lucide-react';
import './FilterBar.css';

const FilterBar = ({ weather = { rain: 0, track_temp: 25, wind: 0 }, tyreDistribution = {} }) => {
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
      className="filter-bar"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="filter-group">
        <span className="filter-label">Weather:</span>
        <div className="weather-filter">
          <CloudRain 
            size={14} 
            style={{ color: getRainColor(weather.rain) }}
          />
          <span 
            className="filter-value"
            style={{ color: getRainColor(weather.rain) }}
          >
            {getRainLevel(weather.rain)}
          </span>
          <span className="filter-separator">|</span>
          <Thermometer size={14} />
          <span className="filter-value">
            {weather.track_temp.toFixed(1)}°C
          </span>
          <span className="filter-separator">|</span>
          <Wind size={14} />
          <span className="filter-value">
            {weather.wind.toFixed(1)} m/s
          </span>
          <span className="filter-separator">|</span>
          <Droplets 
            size={14}
            style={{ color: getRainColor(weather.rain) }}
          />
          <span 
            className="filter-value"
            style={{ color: getRainColor(weather.rain) }}
          >
            {(weather.rain * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      <div className="filter-group">
        <span className="filter-label">Tyres:</span>
        <div className="tyre-filter">
          {Object.entries(tyreDistribution || {}).map(([tyre, count]) => (
            <motion.div
              key={tyre}
              className={`tyre-filter-item ${tyre === recommendation ? 'recommended' : ''}`}
              whileHover={{ scale: 1.05 }}
              transition={{ duration: 0.2 }}
            >
              <div 
                className={`tyre-indicator-small ${tyre === recommendation ? 'recommended-indicator' : ''}`}
                style={{ backgroundColor: getTyreColor(tyre) }}
              ></div>
              <span className={`tyre-filter-name ${tyre === recommendation ? 'recommended-name' : ''}`}>{tyre}</span>
              <span className="tyre-filter-count">{count}</span>
              {tyre === recommendation && (
                <span className="recommended-badge">Recommended</span>
              )}
            </motion.div>
          ))}
        </div>
      </div>

      <div className="filter-group strategy-recommendation">
        <span className="filter-label">Strategy:</span>
        <div className="strategy-content">
          <div 
            className="strategy-tyre-indicator"
            style={{ backgroundColor: getTyreColor(recommendation) }}
          ></div>
          <span 
            className="strategy-value"
            style={{ color: getTyreColor(recommendation) }}
          >
            {recommendation}
          </span>
          <span className="strategy-label">Recommended</span>
        </div>
      </div>
    </motion.div>
  );
};

export default FilterBar;

