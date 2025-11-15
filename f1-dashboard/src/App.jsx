import React, { useState } from 'react';
import { useRaceData } from './hooks/useRaceData';
import TrackView from './components/TrackView';
import Leaderboard from './components/Leaderboard';
import TelemetryPanel from './components/TelemetryPanel';
import RaceStats from './components/RaceStats';
import RaceLog from './components/RaceLog';
import PitLog from './components/PitLog';
import CarDetails from './components/CarDetails';
import ConnectionStatus from './components/ConnectionStatus';
import FilterBar from './components/FilterBar';
import './App.css';

const WS_URL = 'ws://localhost:8000/ws';

function App() {
  const { 
    isConnected, 
    error, 
    trackData, 
    raceState, 
    resetRace 
  } = useRaceData(WS_URL);

  const [selectedCar, setSelectedCar] = useState(null);
  const [showCarDetails, setShowCarDetails] = useState(false);

  // Debug logging
  React.useEffect(() => {
    console.log('App State:', { isConnected, error, hasTrackData: !!trackData, hasCars: raceState.cars?.length });
  }, [isConnected, error, trackData, raceState.cars]);

  const handleCarClick = (carName) => {
    setSelectedCar(carName);
    setShowCarDetails(true);
  };

  const selectedCarData = raceState.cars?.find(c => c.name === selectedCar);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>FORMULA 1 LIVE RACE</h1>
          <p className="subtitle">Real-time Race Simulation & Telemetry</p>
        </div>
      </header>

      <ConnectionStatus 
        isConnected={isConnected} 
        error={error}
        onReset={resetRace}
      />

      <FilterBar
        weather={raceState.weather || { rain: 0, track_temp: 25, wind: 0 }}
        tyreDistribution={raceState.tyre_distribution || {}}
      />

      <div className="dashboard-grid">
        <div className="left-column">
          <div className="track-section">
            {trackData ? (
              <TrackView 
                trackData={trackData} 
                cars={raceState.cars}
                onCarClick={handleCarClick}
              />
            ) : (
              <div className="loading-placeholder">
                <div className="spinner"></div>
                <p>Loading track data...</p>
              </div>
            )}
          </div>

          <div className="log-section">
            <RaceLog 
              cars={raceState.cars || []}
              raceTime={raceState.time || 0}
            />
          </div>

          <div className="pit-log-section">
            <PitLog 
              cars={raceState.cars || []}
              raceTime={raceState.time || 0}
            />
          </div>
        </div>

        <div className="right-column">
          <div className="side-panel">
            <Leaderboard 
              cars={raceState.cars || []}
              raceTime={raceState.time || 0}
              totalLaps={raceState.total_laps || 15}
              onCarClick={handleCarClick}
            />
          </div>

          <div className="stats-section">
            <RaceStats 
              cars={raceState.cars || []}
              raceTime={raceState.time || 0}
            />
          </div>

          <div className="telemetry-section">
            <TelemetryPanel 
              selectedCar={selectedCar}
              cars={raceState.cars || []}
            />
          </div>
        </div>
      </div>

      <CarDetails
        car={selectedCarData}
        isOpen={showCarDetails}
        onClose={() => setShowCarDetails(false)}
      />

      <footer className="app-footer">
        <p>FORMULA 1 RACE SIMULATION | Real-time Telemetry & Data | Powered by WebSocket Technology</p>
      </footer>
    </div>
  );
}

export default App;
