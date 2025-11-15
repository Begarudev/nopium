import React from 'react';
import './ConnectionStatus.css';

const ConnectionStatus = ({ isConnected, error, onReset }) => {
  return (
    <div className="connection-status">
      <div className="status-bar">
        <div className="status-indicator">
          <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
          <span className="status-text">
            {isConnected ? '🟢 Connected to Server' : '🔴 Disconnected'}
          </span>
        </div>
        
        {error && (
          <div className="error-message">
            ⚠️ {error}
          </div>
        )}
        
        <button 
          className="reset-button"
          onClick={onReset}
          disabled={!isConnected}
        >
          🔄 Reset Race
        </button>
      </div>
    </div>
  );
};

export default ConnectionStatus;
