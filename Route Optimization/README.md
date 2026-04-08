# Smart Waste Collection Route Optimization

A production-ready smart city waste management system with real-time IoT bin monitoring, citizen garbage reporting, AI-powered multi-truck route optimization on actual Delhi road networks, and a driver-controlled fleet management interface.

---

## Project Overview

Citizens report waste disposal requests through a mobile app or the admin dashboard. IoT smart bins send real-time fill-level data via ESP32 sensors. The system clusters all garbage locations, computes optimized multi-truck collection routes using real road networks, and deploys a fleet where T1 is driver-controlled and all other trucks run autonomously. Municipal authorities monitor the entire operation live on the admin dashboard.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| Backend | Python, Flask |
| Routing & Optimization | OSMnx, NetworkX, Dijkstra, TSP (brute-force + nearest-neighbor), KMeans |
| Frontend | Leaflet.js, HTML5, CSS3, JavaScript |
| IoT | ESP32, Ultrasonic Sensors, HTTP/WiFi |
| Map Data | OpenStreetMap |

---

## Features

### City Generation
- 65 houses evenly distributed across Delhi using grid-based sampling on real OSMnx road nodes
- Anti-crowding algorithm enforces minimum 50m spacing between houses
- Smart community bins auto-placed near house clusters (1 bin per ~10 houses), snapped to nearest road node
- All locations guaranteed to be on the valid road network

### Garbage Reporting
- Admin can manually toggle any house's garbage status by clicking it on the map
- Citizens register via the user app (phone + map pin), then report garbage during the 2-minute reporting window
- Auto-select feature randomly marks ~35% of houses as having garbage for demo purposes
- IoT bins report FULL/EMPTY status in real time via ESP32 HTTP POST to `/api/bin_status`
- Flexible bin ID matching supports both `B1` and `bin_1` formats

### Route Optimization
- KMeans clustering divides garbage locations into 1–5 zones based on count
- Per-cluster: OSMnx + Dijkstra computes actual road distances between all points
- TSP solved with brute-force for ≤10 stops, nearest-neighbor heuristic for larger sets
- Full road geometry returned as `route_coordinates` for smooth map animation
- Fallback to straight-line nearest-neighbor routing if OSMnx fails

### Fleet Management
- T1 is driver-controlled via the Driver App — moves stop-by-stop, waits for "Collect & Next"
- T2+ trucks are fully autonomous — animated at 150ms/step along their routes
- All trucks start from the Processing Center (North Delhi)
- Route lines shrink in real time as each truck progresses — handled locally via `setLatLngs`, not polling
- Route lines are permanently removed when a truck completes its route
- Per-truck progress bars and efficiency metrics shown in the Fleet Status panel
- Direction-based rotation on truck markers for realistic movement

### Admin Dashboard (`/`)
- Interactive Leaflet map centered on Delhi
- Click any house to toggle its garbage status (admin marking)
- Start/stop the 2-minute citizen reporting window
- Optimize multi-truck routes (triggers clustering + TSP + Dijkstra)
- Deploy fleet — autonomous trucks start immediately, T1 waits for driver
- View mode toggle: show all houses or only optimized route houses
- Fleet Status overlay with per-truck progress bars
- Route metrics: total distance, stops, efficiency %, fuel saved, CO₂ reduced
- Real-time IoT bin notifications (toast alerts when a bin goes FULL)
- Collection History button opens the history page
- Full system reset clears all state while preserving house/bin infrastructure

### Driver App (`/driver`)
- Loads T1's assigned route from the backend
- Truck starts at Processing Center, visits each assigned house in path order
- Automatically stops at each house — driver clicks "Collect & Next" to continue
- Marks each house as collected in the backend (visible on admin map as ✅)
- Progress bar and house list update in real time
- Truck position synced to admin dashboard every 200ms
- Finishes at the Depot
- Auto-reloads on system reset signal

### User App (`/app`)
- Combined register + login interface
- New users pick their location on a map, enter name and phone
- Returning users log in with phone number
- During the reporting window, users see Yes/No garbage buttons
- Reports update the admin dashboard within the next poll cycle

### Collection History (`/history`)
- Full table of all collected locations grouped by truck
- Filter by truck (T1, T2, etc.) or search by location ID
- Summary cards: total collected, trucks active, houses, bins
- Populated from both autonomous truck animation and driver app collections

### IoT Integration
- ESP32 firmware (`esp32_bin_sensor.ino`) reads dual ultrasonic sensors
- Bin marked FULL only after both sensors blocked for 3+ seconds (debounce)
- HTTP POST with retry (3 attempts) to `/api/bin_status`
- WiFi auto-reconnect on disconnect
- Dashboard polls every 3 seconds and shows instant toast notification on FULL status change

---

## Project Structure

```
Route Optimization/
├── smart_waste_demo.py          # Flask backend — all APIs, state, optimization
├── requirements.txt             # Python dependencies
├── esp32_bin_sensor.ino         # ESP32 firmware for physical bin sensors
├── simple_iot.py                # Standalone IoT test server
├── test_iot.py                  # Minimal IoT endpoint for testing
└── templates/
    ├── admin.html               # Operations dashboard
    ├── driver.html              # Driver truck control app
    ├── user_app.html            # Citizen register + report app
    ├── user_registration.html   # Standalone house registration page
    ├── reporting.html           # Citizen reporting interface
    └── history.html             # Collection history viewer
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Admin dashboard |
| GET | `/driver` | Driver app |
| GET | `/app` | User app |
| GET | `/history` | Collection history |
| POST | `/api/optimize_route` | Run clustering + TSP + Dijkstra |
| POST | `/api/spawn_truck` | Deploy fleet, start autonomous movement |
| GET | `/api/get_simulation_status` | Full system state (houses, trucks, routes) |
| POST | `/api/update_truck_position` | Driver app syncs T1 position |
| POST | `/api/mark_house_complete` | Mark a house collected |
| GET | `/api/get_routes` | Get optimized routes for driver app |
| POST | `/api/update_garbage_status` | Admin toggle house garbage status |
| POST | `/api/report_garbage` | Citizen reports garbage |
| POST | `/api/auto_select_garbage` | Auto-mark ~35% houses for demo |
| POST | `/api/start_reporting` | Open 2-minute reporting window |
| POST | `/api/end_reporting` | Close reporting window |
| GET | `/api/reporting_status` | Time remaining in reporting window |
| POST | `/api/bin_status` | IoT ESP32 bin fill-level update |
| POST | `/api/register_house` | Register new citizen house |
| POST | `/api/login_user` | Login by phone number |
| GET | `/api/get_collection_history` | Full collection records |
| POST | `/api/reset_simulation` | Full system reset |
| GET | `/api/system_status` | Reset signal for driver app |

---

## Installation

```bash
git clone https://github.com/Siva-Barath/Route-Optimization-for-Smart-Waste-Management-System.git
cd "Route Optimization"
pip install -r requirements.txt
python smart_waste_demo.py
```

Open `http://localhost:5000` in your browser.

> First run downloads the Delhi road network from OpenStreetMap and caches it. This takes 60–120 seconds. Subsequent runs load from cache instantly.

---

## IoT Setup (ESP32)

1. Flash `esp32_bin_sensor.ino` to your ESP32
2. Set your WiFi credentials and server IP in the sketch:
```cpp
const char* ssid     = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* server_url = "http://<YOUR_PC_IP>:5000/api/bin_status";
const String BIN_ID = "B1";  // Change per bin
```
3. Wire ultrasonic sensors: TRIG1→5, ECHO1→18, TRIG2→17, ECHO2→16
4. Bin is marked FULL when both sensors read < 5cm for 3+ seconds

---

## Workflow

1. Open `http://localhost:5000` — houses and bins load automatically
2. Click **Start Reporting Window** (2 minutes) — citizens can report garbage
3. Click houses on the map to manually mark garbage, or use **Auto Select**
4. Click **Optimize Multi-Truck Routes** — wait 1–2 minutes for TSP + Dijkstra
5. Click **Deploy Truck Fleet** — T2+ start moving autonomously
6. Open **Driver App** for T1 — click Start Route, then Collect & Next at each house
7. Watch routes shrink as trucks progress, checkmarks appear on collected houses
8. View **Collection History** for a full record
9. Click **Reset System** to start a new cycle

---

## Key Metrics

- Houses generated: 65 evenly spread across Delhi on valid road nodes
- Community bins: ~6–7 (1 per 10 houses)
- Route efficiency: TSP saves 20–35% vs naive sequential ordering
- Multi-truck speedup: 60–80% reduction in total collection time vs single truck
- Frontend polling: 3s for house/IoT updates, 500ms for T1 position sync
- IoT response: < 1 second from sensor detection to dashboard notification
- Road network: Full Delhi drive network, filtered to main public roads

---

## Author

Siva Barath S
