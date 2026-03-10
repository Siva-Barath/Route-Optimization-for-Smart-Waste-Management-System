# Smart Waste Collection Route Optimization System

A professional smart city operations dashboard for optimizing garbage collection routes using real road networks and citizen reporting.

## Features

- **City Generation**: Generate 50 random houses across Coimbatore
- **Citizen Reporting**: 30-second reporting window for residents to report garbage availability
- **Route Optimization**: TSP-based route optimization using real OpenStreetMap road networks
- **Real-time Tracking**: Live truck movement visualization with direction-based rotation
- **Professional Dashboard**: Operations dashboard with fleet status, route metrics, and city overview
- **Road-based Routing**: Uses OSMnx and Dijkstra's algorithm for realistic path planning

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: Leaflet.js, HTML5, CSS3
- **Routing**: OSMnx, NetworkX, Scikit-learn
- **Maps**: OpenStreetMap

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Siva-Barath/Route-Optimization-for-Smart-Waste-Management-System.git
cd "Route Optimization"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Flask application:
```bash
python smart_waste_demo.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. **Admin Dashboard**:
   - Click "Generate City" to create 50 houses
   - Click "Start Reporting Window" to open citizen reporting interface
   - Citizens report garbage availability (30 seconds)
   - Click "Optimize Route" to calculate optimal collection path
   - Click "Deploy Truck" to start real-time collection simulation

4. **Reporting Dashboard**:
   - Click houses to report garbage (auto-YES)
   - View real-time statistics
   - Complete reports before timer ends

## How It Works

### Route Optimization
- Loads Coimbatore road network from OpenStreetMap
- Filters roads to keep only main public roads (motorway, trunk, primary, secondary, tertiary, residential)
- Uses Dijkstra's algorithm to compute shortest paths between houses
- Solves Traveling Salesman Problem (TSP) to find optimal visit order
- Generates smooth truck movement along actual road coordinates

### Truck Movement
- Truck follows 200-500 road coordinates per route
- Updates position every 1 second
- Rotates to face direction of travel
- Frontend polls every 0.5 seconds for smooth animation

### UI Design
- Professional operations dashboard (70% map, 30% controls)
- Dark navy header with violet accents
- Real-time statistics and fleet status
- Dashed route visualization with glow effect

## Project Structure

```
Route Optimization/
├── smart_waste_demo.py          # Flask backend
├── requirements.txt              # Python dependencies
└── templates/
    ├── admin.html               # Operations dashboard
    └── reporting.html           # Citizen reporting interface
```

## Key Metrics

- **Road/Straight-line Distance Ratio**: ~1.5-1.6x (proves realistic road following)
- **Route Optimization**: TSP-based with Dijkstra shortest paths
- **Real-time Updates**: 0.5s frontend polling, 1s backend updates

## License

MIT License

## Author

Siva-Barath
