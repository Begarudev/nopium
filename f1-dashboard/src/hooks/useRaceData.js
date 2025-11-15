import { useState, useEffect } from 'react';
import { useWebSocket } from './useWebSocket';

/**
 * Custom hook for managing F1 race data from WebSocket
 * @param {string} wsUrl - WebSocket server URL
 * @returns {Object} - Race state and functions
 */
export const useRaceData = (wsUrl) => {
  const { isConnected, data, error, sendMessage } = useWebSocket(wsUrl);
  
  const [trackData, setTrackData] = useState(null);
  const [raceState, setRaceState] = useState({
    time: 0,
    cars: [],
    weather: { rain: 0, track_temp: 25, wind: 0 },
    total_laps: 15,
    tyre_distribution: {}
  });

  // Fetch track data via HTTP as fallback
  useEffect(() => {
    const fetchTrackData = async () => {
      try {
        const baseUrl = wsUrl.replace('/ws', '').replace('ws://', 'http://').replace('wss://', 'https://');
        const response = await fetch(`${baseUrl}/api/track`);
        if (response.ok) {
          const track = await response.json();
          setTrackData({
            points: track.points || [],
            total_length: track.total_length || 0
          });
        }
      } catch (err) {
        console.error('Failed to fetch track data:', err);
      }
    };

    if (!trackData) {
      fetchTrackData();
    }
  }, [trackData, wsUrl]);

  useEffect(() => {
    if (data) {
      if (data.type === 'track' && data.data) {
        setTrackData(data.data);
      } else if (data.time !== undefined) {
        // Regular race state update
        setRaceState(data);
      }
    }
  }, [data]);

  const resetRace = () => {
    sendMessage({ type: 'reset' });
  };

  return {
    isConnected,
    error,
    trackData,
    raceState,
    resetRace,
  };
};
