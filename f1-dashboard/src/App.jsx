import React, { useState, useEffect, useRef } from 'react';
import { useRaceData } from './hooks/useRaceData';
import TrackView from './components/TrackView';
import Leaderboard from './components/Leaderboard';
import TelemetryPanel from './components/TelemetryPanel';
import RaceStats from './components/RaceStats';
import RaceLog from './components/RaceLog';
import PitLog from './components/PitLog';
import CarDetails from './components/CarDetails';
import RaceInsightsModal from './components/RaceInsightsModal';
import RaceDashboard from './components/RaceDashboard';
import ConnectionStatus from './components/ConnectionStatus';
import FilterBar from './components/FilterBar';
import WeatherSelector from './components/WeatherSelector';
import StartRaceButton from './components/StartRaceButton';
import SimulationControls from './components/SimulationControls';
import { pageLoadReveal, speedLines } from './utils/animations';
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
  const [showRaceInsights, setShowRaceInsights] = useState(false);
  const [showRaceDashboard, setShowRaceDashboard] = useState(false);
  const [raceInsights, setRaceInsights] = useState({});
  const [selectedWeather, setSelectedWeather] = useState({
    rain: 0.0,
    track_temp: 25.0,
    wind: 0.0
  });
  const [raceStarted, setRaceStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const appRef = useRef(null);
  const headerRef = useRef(null);
  const dashboardRef = useRef(null);
  const rightColumnRef = useRef(null);
  const audioRef = useRef(null);
  const currentSongRef = useRef(null);

  // Page load animations
  useEffect(() => {
    if (appRef.current) {
      pageLoadReveal(appRef.current, { duration: 1500 });
    }
    if (headerRef.current) {
      // Speed lines in header
      const speedLineInterval = setInterval(() => {
        speedLines(headerRef.current, { 
          duration: 2000, 
          direction: 'horizontal',
          intensity: 0.5 
        });
      }, 3000);
      return () => clearInterval(speedLineInterval);
    }
  }, []);

  // Update raceStarted from WebSocket state
  useEffect(() => {
    if (raceState.race_started !== undefined) {
      setRaceStarted(raceState.race_started);
    }
  }, [raceState.race_started]);

  // Initialize selectedWeather from raceState only once when weather first becomes available
  const weatherInitialized = React.useRef(false);
  const prevWeatherRef = React.useRef(null);
  
  useEffect(() => {
    // Initialize once when weather first becomes available
    if (raceState.weather && !weatherInitialized.current) {
      setSelectedWeather(raceState.weather);
      weatherInitialized.current = true;
      prevWeatherRef.current = raceState.weather;
    }
    // Update when race finishes to show actual race weather
    else if (raceState.race_finished && raceState.weather && prevWeatherRef.current !== raceState.weather) {
      setSelectedWeather(raceState.weather);
      prevWeatherRef.current = raceState.weather;
    }
  }, [raceState.weather, raceState.race_finished]);

  // Fetch race insights when race finishes and show dashboard
  useEffect(() => {
    if (raceState.race_finished && !showRaceDashboard) {
      const fetchInsights = async () => {
        try {
          const response = await fetch('http://localhost:8000/api/race-insights');
          if (response.ok) {
            const data = await response.json();
            setRaceInsights(data.insights || {});
            setShowRaceDashboard(true);
          }
        } catch (error) {
          console.error('Failed to fetch race insights:', error);
        }
      };
      fetchInsights();
    }
  }, [raceState.race_finished, showRaceDashboard]);

  // Debug logging
  React.useEffect(() => {
    console.log('App State:', { isConnected, error, hasTrackData: !!trackData, hasCars: raceState.cars?.length });
  }, [isConnected, error, trackData, raceState.cars]);

  // Music playback based on leaderboard position
  useEffect(() => {
    // Only play music when race is started and not finished
    if (!raceStarted || raceState.race_finished || !raceState.cars || raceState.cars.length === 0) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      currentSongRef.current = null;
      return;
    }

    // Find the first-ranked driver
    const sortedCars = [...raceState.cars].sort((a, b) => (a.position || 0) - (b.position || 0));
    const leader = sortedCars[0];
    
    if (!leader) return;

    const isMaxFirst = leader.name === 'Max Verstappen';
    const targetSong = isMaxFirst 
      ? '/music/tu-tu-tu-du-max-verstappen.mp3'
      : '/music/f1_theme_brian_tyler.mp3';

    // Only switch songs if the target song has changed
    if (currentSongRef.current === targetSong) {
      // If audio is paused but should be playing, resume it
      if (audioRef.current && audioRef.current.paused) {
        audioRef.current.play().catch(err => {
          console.error('Error playing audio:', err);
        });
      }
      return;
    }

    // Stop current audio if playing
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }

    // Create new audio element
    const audio = new Audio(targetSong);
    audio.loop = true;
    audio.volume = 0.5; // Set volume to 50%
    
    audioRef.current = audio;
    currentSongRef.current = targetSong;

    // Play the new song
    audio.play().catch(err => {
      console.error('Error playing audio:', err);
    });

    // Cleanup function
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
    };
  }, [raceState.cars, raceStarted, raceState.race_finished]);

  const handleWeatherChange = (newWeather) => {
    setSelectedWeather(newWeather);
  };

  const handleStartRace = async () => {
    // If race is in progress, pause it
    if (raceStarted && !raceState.race_finished) {
      setLoading(true);
      try {
        const response = await fetch('http://localhost:8000/api/pause', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          throw new Error('Failed to pause race');
        }

        const data = await response.json();
        setRaceStarted(false);
        console.log('Race paused:', data);
      } catch (error) {
        console.error('Error pausing race:', error);
        alert('Failed to pause race. Please try again.');
      } finally {
        setLoading(false);
      }
      return;
    }

    // If race finished, reset first
    if (raceState.race_finished) {
      resetRace();
      setRaceStarted(false);
      setShowRaceDashboard(false);
      setRaceInsights({});
      weatherInitialized.current = false; // Reset initialization flag for new race
      // Wait a bit for reset to complete
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(selectedWeather),
      });

      if (!response.ok) {
        throw new Error('Failed to start race');
      }

      const data = await response.json();
      setRaceStarted(true);
      console.log('Race started:', data);
    } catch (error) {
      console.error('Error starting race:', error);
      alert('Failed to start race. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCarClick = (carName) => {
    setSelectedCar(carName);
    setShowCarDetails(true);
  };

  const selectedCarData = raceState.cars?.find(c => c.name === selectedCar);

  const handleResetFromDashboard = () => {
    resetRace();
    setRaceStarted(false);
    setShowRaceDashboard(false);
    setRaceInsights({});
    weatherInitialized.current = false;
  };

  const handleBackFromDashboard = () => {
    setShowRaceDashboard(false);
  };

  // Show Race Dashboard when race is finished
  if (showRaceDashboard && raceState.race_finished) {
    return (
      <div className="app" ref={appRef}>
        <RaceDashboard
          insights={raceInsights}
          undercutSummary={raceState.undercut_summary || []}
          raceState={raceState}
          onReset={handleResetFromDashboard}
          onBack={handleBackFromDashboard}
        />
      </div>
    );
  }

  return (
    <div className="app" ref={appRef}>
      <header className="app-header" ref={headerRef}>
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

      {!raceStarted && (
        <div className="race-controls-section">
          <WeatherSelector
            weather={selectedWeather}
            onWeatherChange={handleWeatherChange}
            disabled={false}
          />
          <div className="start-button-container">
            <StartRaceButton
              onStart={handleStartRace}
              disabled={!isConnected}
              raceStarted={raceStarted}
              raceFinished={raceState.race_finished || false}
              loading={loading}
            />
          </div>
        </div>
      )}

      {raceStarted && !raceState.race_finished && (
        <div className="race-in-progress-controls">
          <SimulationControls 
            wsUrl={WS_URL}
            raceStarted={raceStarted}
            raceFinished={raceState.race_finished || false}
          />
        </div>
      )}

      {raceState.race_finished && !showRaceDashboard && (
        <div className="race-controls-section">
          <div className="start-button-container">
            <StartRaceButton
              onStart={handleStartRace}
              disabled={!isConnected}
              raceStarted={raceStarted}
              raceFinished={raceState.race_finished || false}
              loading={loading}
            />
          </div>
        </div>
      )}

      <FilterBar
        weather={raceState.weather || selectedWeather}
        tyreDistribution={raceState.tyre_distribution || {}}
      />

      <div className="dashboard-grid" ref={dashboardRef}>
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
              raceFinished={raceState.race_finished || false}
              undercutSummary={raceState.undercut_summary || []}
              raceEvents={raceState.race_events || []}
            />
          </div>

          <div className="pit-log-section">
            <PitLog 
              cars={raceState.cars || []}
              raceTime={raceState.time || 0}
            />
          </div>
        </div>

        <div className="right-column" ref={rightColumnRef}>
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
        containerRef={rightColumnRef}
      />

      <RaceInsightsModal
        isOpen={showRaceInsights}
        onClose={() => setShowRaceInsights(false)}
        onReset={() => {
          resetRace();
          setRaceStarted(false);
          setShowRaceInsights(false);
          setRaceInsights({});
          weatherInitialized.current = false;
        }}
        insights={raceInsights}
      />

      <footer className="app-footer">
        <p>FORMULA 1 RACE SIMULATION | Real-time Telemetry & Data | Powered by WebSocket Technology</p>
      </footer>
    </div>
  );
}

export default App;
