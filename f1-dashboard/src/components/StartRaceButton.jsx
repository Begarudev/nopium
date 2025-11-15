import React from 'react';
import { Play, Pause, RotateCcw, Loader } from 'lucide-react';
import './StartRaceButton.css';

const StartRaceButton = ({ onStart, disabled = false, raceStarted = false, raceFinished = false, loading = false }) => {
  const getButtonContent = () => {
    if (loading) {
      return (
        <>
          <Loader className="button-icon spinning" size={20} />
          <span>Starting...</span>
        </>
      );
    }
    
    if (raceFinished) {
      return (
        <>
          <RotateCcw className="button-icon" size={20} />
          <span>New Race</span>
        </>
      );
    }
    
    if (raceStarted) {
      return (
        <>
          <Pause className="button-icon" size={20} />
          <span>Race In Progress...</span>
        </>
      );
    }
    
    return (
      <>
        <Play className="button-icon" size={20} />
        <span>Start Race</span>
      </>
    );
  };

  const getButtonClass = () => {
    let baseClass = 'start-race-button';
    if (raceFinished) baseClass += ' finished';
    else if (raceStarted) baseClass += ' in-progress';
    else baseClass += ' ready';
    if (disabled || loading) baseClass += ' disabled';
    return baseClass;
  };

  return (
    <button
      className={getButtonClass()}
      onClick={onStart}
      disabled={disabled || loading}
      type="button"
    >
      {getButtonContent()}
    </button>
  );
};

export default StartRaceButton;

