# Smart Waste Collection Demo

A Flask-based demonstration of an intelligent waste collection system that optimizes garbage truck routes for efficient city-wide collection.

## Features

- **City Generation**: Automatically generates houses and depot locations
- **Garbage Reporting**: Residents report garbage status via web interface
- **Route Optimization**: Calculates optimal collection route using TSP algorithm
- **Automatic Truck Movement**: Truck follows optimized route automatically
- **Real-time Tracking**: Live map visualization of truck position
- **Garbage Collection**: Interactive collection at each house

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the demo**:
   ```bash
   python smart_waste_demo.py
   ```

3. **Open in browser**:
   Navigate to `http://localhost:5000`

## Demo Workflow

1. **Generate City**: Creates random house locations and depot
2. **Start Reporting**: Opens 30-second window for residents to report garbage
3. **Report Garbage**: Click houses to report garbage (automatic YES selection)
4. **Optimize Route**: Calculates optimal TSP route through all garbage houses
5. **Spawn Truck**: Truck appears at depot and begins automatic movement
6. **Follow Collection**: Watch truck move along optimized route
7. **Collect Garbage**: Press 'C' when truck stops at garbage houses

## Architecture

### Backend (Flask)
- **City Generator**: Creates random house coordinates
- **Route Optimizer**: Implements TSP algorithm for efficient routing
- **Truck Controller**: Background thread moves truck every 3 seconds
- **API Endpoints**: RESTful API for frontend communication

### Frontend (Leaflet.js)
- **Interactive Map**: Visual representation of city and routes
- **Real-time Updates**: Polls backend every 1.5 seconds
- **Automatic Collection**: Truck follows optimized route automatically
- **User Interface**: Bootstrap-based responsive design

## API Endpoints

- `GET /` - Admin interface
- `GET /reporting` - Resident reporting interface
- `POST /api/generate_city` - Generate new city
- `POST /api/start_reporting` - Start garbage reporting window
- `POST /api/update_garbage_status` - Update house garbage status
- `POST /api/end_reporting` - End reporting window
- `POST /api/optimize_route` - Calculate optimal collection route
- `POST /api/spawn_truck` - Spawn truck and start movement
- `GET /api/get_simulation_status` - Get current simulation state
- `POST /api/collect_garbage` - Collect garbage from house

## Technologies

- **Backend**: Python 3.x, Flask, Threading
- **Frontend**: HTML5, JavaScript, Leaflet.js, Bootstrap 5
- **Algorithms**: Traveling Salesman Problem (TSP) optimization
- **Mapping**: OpenStreetMap with Leaflet.js

## Project Structure

```
smart-waste-demo/
├── smart_waste_demo.py          # Main Flask application
├── requirements.txt             # Python dependencies
├── README.md                 # This file
└── templates/
    └── admin.html              # Admin interface
    └── reporting.html           # Resident reporting interface
```

## License

MIT License - Free for commercial and personal use
