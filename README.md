# Smart Waste Collection Route Optimization Prototype

A prototype dashboard demonstrating AI-assisted route optimization for smart waste collection, designed as part of an intelligent waste management system for smart cities.

This module focuses on optimizing garbage truck routes based on reported waste locations using real road networks.

## Project Overview

This prototype demonstrates the route optimization and fleet monitoring module of a larger Smart Waste Management System.

In the full system architecture:
- Citizens report waste disposal requests through a mobile application
- These reports are sent to the backend and visualized on the operations dashboard
- The system generates an optimized garbage collection route
- Municipal authorities monitor the truck's real-time movement

Since the mobile application and optimization system are currently developed separately, this prototype simulates citizen reporting directly from the dashboard.

## Key Features

### Simulated Citizen Reporting
- Houses can manually report garbage disposal requests
- These represent locations where waste collection is required
- In the final system, this data will come from the citizen mobile application in real time

### Route Optimization Engine
- Calculates the most efficient route for garbage collection trucks
- Minimizes travel distance, fuel consumption, and collection time

### Real Road-Network Routing
- Uses OpenStreetMap road networks instead of straight-line distance
- Ensures realistic path planning for urban environments

### Truck Deployment Simulation
- The truck starts from a depot
- Travels along the optimized route
- Collects waste from reported houses
- Reaches the processing facility automatically

### Live Dashboard Visualization
- Displays houses, collection points, and routes on an interactive map
- Shows truck movement and route progress
- Professional operations dashboard with real-time metrics

## Tech Stack

### Backend
- Python
- Flask

### Routing & Optimization
- OSMnx – Road network extraction from OpenStreetMap
- NetworkX – Graph-based path computation
- Dijkstra Algorithm – Shortest path calculation
- TSP Optimization – Optimal visit sequence

### Frontend
- Leaflet.js
- HTML5
- CSS3

### Map Data
- OpenStreetMap

## How the System Works

### 1. Waste Reporting
Citizens report garbage disposal requests through a mobile application. For this prototype, waste reporting is simulated by selecting houses directly on the dashboard.

### 2. Data Processing
Reported locations are collected as garbage pickup points.

### 3. Route Optimization
The system:
- Loads the road network from OpenStreetMap
- Computes shortest paths using Dijkstra's algorithm
- Solves a Traveling Salesman Problem (TSP) to determine the best order of house visits
- Generates an optimized collection route

### 4. Truck Deployment
The truck is deployed from the depot and follows the optimized route automatically, visiting all collection points.

### 5. Future Real-Time Tracking
In the real system:
- Garbage trucks will be equipped with GPS trackers
- The truck's location will be sent to the dashboard in real time
- Authorities can monitor live collection progress

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

3. Run the application:
```bash
python smart_waste_demo.py
```

4. Open in browser:
```
http://localhost:5000
```

## Dashboard Workflow

1. **Generate City** - Create 50 random houses across Coimbatore
2. **Start Reporting Window** - Open citizen reporting interface (30 seconds)
3. **Report Garbage** - Citizens click houses to report waste availability
4. **Optimize Route** - Calculate optimal collection path using TSP + Dijkstra
5. **Deploy Truck** - Start real-time truck movement simulation
6. **Monitor Progress** - Watch truck follow optimized route on map

## Project Structure

```
Route Optimization/
├── smart_waste_demo.py          # Flask backend with route optimization
├── requirements.txt              # Python dependencies
└── templates/
    ├── admin.html               # Operations dashboard
    └── reporting.html           # Citizen reporting interface
```

## Key Metrics

- **Road/Straight-line Distance Ratio**: ~1.5-1.6x (proves realistic road following)
- **Route Optimization**: TSP-based with Dijkstra shortest paths
- **Real-time Updates**: 0.5s frontend polling, 1s backend updates
- **Truck Rotation**: Direction-based rotation for realistic movement visualization

## Future Integration

This prototype will later be integrated with:
- Citizen mobile reporting application
- AI waste classification system
- Real-time GPS truck tracking
- Segregation-based reward system
- Integration with municipal waste management systems

to create a complete intelligent waste management platform.

## License

MIT License

## Author

Siva Barath S
