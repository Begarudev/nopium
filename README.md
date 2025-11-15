# F1 Live Race Dashboard 🏎️

A real-time Formula 1 race simulator with WebSocket communication, featuring a beautiful React dashboard with hooks.

## Features

- ✅ **Real-time WebSocket Communication**: Live data streaming from Python backend to React frontend
- ✅ **React Hooks**: Modern functional components with custom hooks for WebSocket and race data
- ✅ **Beautiful UI**: Gradient backgrounds, smooth animations, and responsive design
- ✅ **Live Track Visualization**: Canvas-based rendering of cars on track
- ✅ **Dynamic Leaderboard**: Real-time position updates with tyre strategy and wear indicators
- ✅ **Weather System**: Rain, temperature, and wind affecting race conditions
- ✅ **Auto-reconnect**: Automatic WebSocket reconnection with exponential backoff

## Architecture

### Backend (Python)
- **FastAPI**: Web framework with WebSocket support
- **Simulation Engine**: Physics-based F1 race simulation
- **Broadcasting**: Real-time state updates to all connected clients

### Frontend (React)
- **Custom Hooks**: 
  - `useWebSocket` - WebSocket connection management
  - `useRaceData` - Race state management
- **Components**:
  - `TrackView` - Canvas-based track and car rendering
  - `Leaderboard` - Live standings with detailed stats
  - `WeatherPanel` - Weather and tyre distribution
  - `ConnectionStatus` - Connection monitoring and reset controls

## Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Start the WebSocket server:
```bash
python server.py
```

The server will run on `http://localhost:8000`

### Frontend Setup

1. Navigate to the dashboard directory:
```bash
cd f1-dashboard
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The dashboard will open at `http://localhost:3000`

## Usage

1. **Start Backend**: Run `python server.py`
2. **Start Frontend**: In another terminal, run `cd f1-dashboard && npm run dev`
3. **Open Browser**: Navigate to `http://localhost:3000`
4. **Watch the Race**: Real-time updates will stream automatically
5. **Reset Race**: Click the "Reset Race" button to restart the simulation

## WebSocket Protocol

### Server → Client Messages

```json
{
  "time": 125.5,
  "cars": [
    {
      "name": "Hamilton",
      "position": 1,
      "laps": 5,
      "wear": 0.234,
      "tyre": "SOFT",
      "fuel": 87.5,
      "speed": 234.2,
      "x": 450.0,
      "y": 320.0,
      "angle": 1.57,
      "total_time": 120.5,
      "on_pit": false
    }
  ],
  "weather": {
    "rain": 0.15,
    "track_temp": 22.0,
    "wind": 3.0
  },
  "total_laps": 15,
  "tyre_distribution": {
    "SOFT": 3,
    "MEDIUM": 5,
    "HARD": 2
  }
}
```

### Client → Server Messages

```json
{
  "type": "reset"
}
```

## Project Structure

```
.
├── server.py                 # FastAPI WebSocket server
├── nice.py                   # Original matplotlib simulation
├── requirements.txt          # Python dependencies
├── f1-dashboard/
│   ├── src/
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js    # WebSocket hook
│   │   │   └── useRaceData.js     # Race data hook
│   │   ├── components/
│   │   │   ├── TrackView.jsx      # Track visualization
│   │   │   ├── Leaderboard.jsx    # Live standings
│   │   │   ├── WeatherPanel.jsx   # Weather info
│   │   │   └── ConnectionStatus.jsx
│   │   ├── App.jsx
│   │   └── index.jsx
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Technologies Used

### Backend
- FastAPI - Modern async web framework
- Uvicorn - ASGI server
- NumPy - Numerical computing
- SciPy - Scientific computing (spline interpolation)

### Frontend
- React 18 - UI library with hooks
- Vite - Fast build tool
- Canvas API - Track rendering
- WebSocket API - Real-time communication

## Performance

- **Update Rate**: 10 updates/second from server
- **Latency**: <50ms typical WebSocket latency
- **Auto-reconnect**: Exponential backoff up to 30 seconds

## Future Enhancements

- [ ] Multiple race circuits selection
- [ ] Pit stop strategy controls
- [ ] Telemetry graphs (speed, throttle, brake)
- [ ] Race replay system
- [ ] Multi-user spectator mode
- [ ] Driver AI difficulty settings

## License

MIT

## Author

Built with ❤️ using React Hooks + WebSockets
