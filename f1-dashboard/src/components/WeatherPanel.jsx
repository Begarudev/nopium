import React from 'react';
import { motion } from 'framer-motion';
import './WeatherPanel.css';

const WeatherPanel = ({ weather = { rain: 0, track_temp: 25, wind: 0 } }) => {

  return (
    <motion.div
      className="weather-panel"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="weather-section">
        <h3>Weather Effects</h3>
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

    </motion.div>
  );
};

export default WeatherPanel;
