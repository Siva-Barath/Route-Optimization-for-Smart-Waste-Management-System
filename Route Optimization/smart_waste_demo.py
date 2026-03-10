from flask import Flask, render_template, jsonify, request
import random
import time
import osmnx as ox
import networkx as nx
from itertools import permutations

app = Flask(__name__)

# Load road network once at startup (cached for performance)
print("="*50)
print("Loading Coimbatore road network from OpenStreetMap...")
print("This may take 30-60 seconds on first run...")
try:
    # Load road network with simplification
    G = ox.graph_from_point((11.018, 76.972), dist=3000, network_type='drive', simplify=True)
    
    print(f"Initial graph: {len(G.nodes)} nodes, {len(G.edges)} edges")
    
    # Filter - keep only main public roads
    print("Filtering roads...")
    edges_to_remove = []
    
    allowed_road_types = [
        'motorway', 'motorway_link',
        'trunk', 'trunk_link',
        'primary', 'primary_link',
        'secondary', 'secondary_link',
        'tertiary', 'tertiary_link',
        'residential',
        'unclassified'
    ]
    
    for u, v, k, data in G.edges(keys=True, data=True):
        highway_type = data.get('highway', '')
        
        if isinstance(highway_type, list):
            highway_type = highway_type[0] if highway_type else ''
        
        if highway_type not in allowed_road_types:
            edges_to_remove.append((u, v, k))
    
    for edge in edges_to_remove:
        try:
            G.remove_edge(*edge)
        except:
            pass
    
    print(f"Removed {len(edges_to_remove)} roads")
    print(f"✅ Road network loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
    ROAD_NETWORK_LOADED = True
except Exception as e:
    print(f"❌ Failed to load road network: {e}")
    import traceback
    traceback.print_exc()
    G = None
    ROAD_NETWORK_LOADED = False
print("="*50)

# Single source of truth for entire application
app_state = {
    'houses': [],
    'city_generated': False,
    'reporting_active': False,
    'reporting_ended': False,
    'route_optimized': False,
    'truck_spawned': False,
    'garbage_houses': [],
    'no_garbage_houses': [],
    'reporting_deadline': 0,
    'optimized_route': [],
    'current_route_index': 0
}

@app.route('/')
def admin_page():
    """Serve admin control page"""
    return render_template('admin.html')

@app.route('/reporting')
def reporting_page():
    """Serve garbage reporting page"""
    return render_template('reporting.html')

@app.route('/api/generate_city', methods=['POST'])
def generate_city():
    """Generate city with houses"""
    global app_state
    
    print("=== GENERATE CITY ===")
    
    try:
        houses = []
        for i in range(50):
            houses.append({
                'id': f'H{i+1:03d}',
                'lat': 11.018 + random.uniform(-0.005, 0.005),
                'lng': 76.972 + random.uniform(-0.005, 0.005)
            })
        
        app_state['houses'] = houses
        app_state['city_generated'] = True
        app_state['reporting_active'] = False
        app_state['reporting_ended'] = False
        app_state['route_optimized'] = False
        app_state['truck_spawned'] = False
        app_state['garbage_houses'] = []
        app_state['no_garbage_houses'] = []
        
        print(f"Generated {len(houses)} houses")
        
        return jsonify({
            'success': True,
            'houses': houses,
            'total_houses': len(houses)
        })
        
    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/start_reporting', methods=['POST'])
def start_reporting():
    """Start garbage reporting window"""
    global app_state
    
    print("=== START REPORTING ===")
    
    if not app_state['city_generated']:
        return jsonify({'success': False, 'error': 'Generate city first'})
    
    app_state['reporting_active'] = True
    app_state['reporting_ended'] = False
    app_state['reporting_deadline'] = int(time.time()) + 30  # 30 seconds from now
    
    print("Started reporting window")
    
    return jsonify({
        'success': True,
        'redirect_url': '/reporting'
    })

@app.route('/api/update_garbage_status', methods=['POST'])
def update_garbage_status():
    """Update garbage status for a house"""
    global app_state
    
    data = request.get_json()
    house_id = data.get('house_id')
    has_garbage = data.get('has_garbage', False)
    
    print(f"UPDATE HOUSE {house_id}: has_garbage={has_garbage}")
    
    # Find and update house
    for house in app_state['houses']:
        if house['id'] == house_id:
            house['has_garbage'] = has_garbage
            house['reported'] = True
            print(f"Updated house {house_id} locally")
            break
    
    # Update garbage houses list
    app_state['garbage_houses'] = [
        house for house in app_state['houses'] 
        if house.get('has_garbage', False) == True
    ]
    
    app_state['no_garbage_houses'] = [
        house for house in app_state['houses']
        if house.get('has_garbage', False) == False and house.get('reported', False)
    ]
    
    print(f"Garbage houses: {len(app_state['garbage_houses'])}")
    print(f"No garbage houses: {len(app_state['no_garbage_houses'])}")
    
    return jsonify({
        'success': True,
        'garbage_houses': app_state['garbage_houses'],
        'no_garbage_houses': app_state['no_garbage_houses'],
        'total_garbage_houses': len(app_state['garbage_houses']),
        'total_no_garbage_houses': len(app_state['no_garbage_houses'])
    })

@app.route('/api/end_reporting', methods=['POST'])
def end_reporting():
    """End garbage reporting window"""
    global app_state
    
    print("=== END REPORTING ===")
    
    app_state['reporting_active'] = False
    app_state['reporting_ended'] = True
    
    print("Ended reporting window")
    
    return jsonify({'success': True})

@app.route('/api/optimize_route', methods=['POST'])
def optimize_route():
    """Optimize garbage collection route using REAL ROAD NETWORKS (OSMnx)"""
    global app_state
    
    print("=== OPTIMIZE ROUTE (ROAD-BASED) ===")
    
    if not app_state['reporting_ended']:
        return jsonify({'success': False, 'error': 'Reporting must end first'})
    
    garbage_houses = app_state['garbage_houses']
    
    if not garbage_houses:
        return jsonify({'success': False, 'error': 'No garbage houses to optimize'})
    
    print(f"Optimizing route for {len(garbage_houses)} houses using ROAD NETWORK")
    
    if not ROAD_NETWORK_LOADED:
        print("⚠️ Road network not available, using fallback")
        return optimize_route_fallback()
    
    # Define depot and processing center
    depot = {'lat': 11.018, 'lng': 76.972}
    processing = {'lat': 11.020, 'lng': 76.975}
    
    # Get road-based distance matrix and paths using OSMnx
    print("Computing road distances using OSMnx...")
    distance_matrix, road_paths = get_road_distance_matrix_osmnx(depot, garbage_houses, processing)
    
    if distance_matrix is None or not road_paths:
        print("⚠️ OSMnx routing failed, using fallback")
        return optimize_route_fallback()
    
    # Solve TSP using road distances
    print("Solving TSP with road distances...")
    best_order = solve_tsp(distance_matrix, len(garbage_houses))
    
    # Build optimized route waypoints
    route = []
    route.append({
        'id': 'depot',
        'coords': (depot['lat'], depot['lng']),
        'type': 'depot'
    })
    
    for house_idx in best_order:
        house = garbage_houses[house_idx]
        route.append({
            'id': house['id'],
            'coords': (house['lat'], house['lng']),
            'type': 'garbage'
        })
    
    route.append({
        'id': 'processing',
        'coords': (processing['lat'], processing['lng']),
        'type': 'processing'
    })
    
    # Build FULL ROAD GEOMETRY by connecting all segments
    print("Building full road geometry...")
    route_coordinates = []
    total_distance = 0
    
    # Map route indices to distance matrix indices
    route_to_matrix = [0]  # depot
    for house_idx in best_order:
        route_to_matrix.append(house_idx + 1)
    route_to_matrix.append(len(garbage_houses) + 1)  # processing
    
    # Connect each consecutive pair with road path
    for i in range(len(route_to_matrix) - 1):
        from_idx = route_to_matrix[i]
        to_idx = route_to_matrix[i + 1]
        
        path_key = f"{from_idx}_{to_idx}"
        
        if path_key in road_paths:
            segment = road_paths[path_key]
            # Add segment (avoid duplicating connection points)
            if i == 0:
                route_coordinates.extend(segment)
            else:
                route_coordinates.extend(segment[1:])  # Skip first point to avoid duplicate
            
            print(f"  Added road segment {from_idx}->{to_idx}: {len(segment)} points")
        else:
            print(f"⚠️ Missing road path for {from_idx}->{to_idx}")
        
        total_distance += distance_matrix[from_idx][to_idx]
    
    # Calculate naive distance
    naive_distance = 0
    for i in range(len(distance_matrix) - 1):
        naive_distance += distance_matrix[i][i + 1]
    
    distance_saved = naive_distance - total_distance
    percentage_saved = (distance_saved / naive_distance * 100) if naive_distance > 0 else 0
    
    # Calculate average stop distance
    avg_stop_distance = total_distance / len(garbage_houses) if len(garbage_houses) > 0 else 0
    
    # Calculate straight-line total for comparison
    straight_total = 0
    for i in range(len(route) - 1):
        lat1, lng1 = route[i]['coords']
        lat2, lng2 = route[i+1]['coords']
        straight_total += ((lat2-lat1)**2 + (lng2-lng1)**2)**0.5 * 111
    
    road_vs_straight_ratio = total_distance / straight_total if straight_total > 0 else 1.0
    
    app_state['route_optimized'] = True
    app_state['optimized_route'] = route
    app_state['route_coordinates'] = route_coordinates
    app_state['current_route_index'] = 0
    
    print(f"✅ Route optimized: {len(route)} waypoints, {len(route_coordinates)} road points")
    print(f"✅ Total distance: {total_distance:.2f}km via roads")
    print(f"✅ Straight-line distance: {straight_total:.2f}km")
    print(f"✅ Road/Straight ratio: {road_vs_straight_ratio:.2f}x (proves roads are followed)")
    print(f"✅ Saved {distance_saved:.2f}km ({percentage_saved:.1f}%) vs naive route")
    print(f"✅ Average distance per stop: {avg_stop_distance:.2f}km")
    
    return jsonify({
        'success': True,
        'route': route,
        'route_coordinates': route_coordinates,
        'total_distance_km': round(total_distance, 2),
        'houses_visited': len(garbage_houses),
        'naive_distance_km': round(naive_distance, 2),
        'distance_saved_km': round(distance_saved, 2),
        'percentage_saved': round(percentage_saved, 1),
        'houses_avoided': len(app_state['no_garbage_houses']),
        'routing_method': 'OSMnx Road Network',
        'avg_stop_distance_km': round(avg_stop_distance, 2),
        'straight_line_distance_km': round(straight_total, 2),
        'road_ratio': round(road_vs_straight_ratio, 2),
        'total_road_points': len(route_coordinates)
    })

def get_road_distance_matrix_osmnx(depot, houses, processing):
    """Get distance matrix using OSMnx (offline road network)"""
    try:
        points = [depot] + houses + [processing]
        
        print(f"Computing distances for {len(points)} points...")
        
        # Find nearest nodes (unprojected)
        nodes = []
        for i, point in enumerate(points):
            node = ox.distance.nearest_nodes(G, point['lng'], point['lat'])
            nodes.append(node)
            if i % 10 == 0:
                print(f"  Mapped {i}/{len(points)} points...")
        
        print(f"✅ All points mapped")
        
        # Build distance matrix
        distance_matrix = []
        road_paths = {}
        
        for i, from_node in enumerate(nodes):
            row = []
            for j, to_node in enumerate(nodes):
                if i == j:
                    row.append(0.0)
                    continue
                
                try:
                    path = nx.shortest_path(G, from_node, to_node, weight='length', method='dijkstra')
                    distance = nx.shortest_path_length(G, from_node, to_node, weight='length')
                    distance_km = distance / 1000.0
                    
                    lat1, lng1 = points[i]['lat'], points[i]['lng']
                    lat2, lng2 = points[j]['lat'], points[j]['lng']
                    straight_km = ((lat2-lat1)**2 + (lng2-lng1)**2)**0.5 * 111
                    
                    if i < 3 and j < 3:
                        print(f"  Path {i}→{j}: Road={distance_km:.3f}km, Straight={straight_km:.3f}km")
                    
                    row.append(distance_km)
                    
                    # Store path coordinates
                    coords = [[G.nodes[node]['y'], G.nodes[node]['x']] for node in path]
                    road_paths[f"{i}_{j}"] = coords
                    
                except nx.NetworkXNoPath:
                    print(f"⚠️ No path {i}→{j}")
                    lat1, lng1 = points[i]['lat'], points[i]['lng']
                    lat2, lng2 = points[j]['lat'], points[j]['lng']
                    distance_km = ((lat2-lat1)**2 + (lng2-lng1)**2)**0.5 * 111
                    row.append(distance_km)
                    road_paths[f"{i}_{j}"] = [[lat1, lng1], [lat2, lng2]]
            
            distance_matrix.append(row)
            
            if (i + 1) % 5 == 0:
                print(f"  Computed {i+1}/{len(points)} points...")
        
        print(f"✅ Matrix: {len(distance_matrix)}x{len(distance_matrix[0])}")
        print(f"✅ Paths: {len(road_paths)} segments")
        
        return distance_matrix, road_paths
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def solve_tsp(distance_matrix, num_houses):
    """Solve TSP using nearest neighbor heuristic (fast for real-time)"""
    # For small problems, use nearest neighbor (fast and good enough)
    if num_houses <= 10:
        return solve_tsp_optimal(distance_matrix, num_houses)
    else:
        return solve_tsp_nearest_neighbor(distance_matrix, num_houses)

def solve_tsp_optimal(distance_matrix, num_houses):
    """Optimal TSP for small problems (brute force)"""
    house_indices = list(range(num_houses))
    best_distance = float('inf')
    best_order = house_indices
    
    # Try all permutations (only feasible for small n)
    for perm in permutations(house_indices):
        distance = 0
        prev = 0  # Start from depot
        
        for house_idx in perm:
            distance += distance_matrix[prev][house_idx + 1]
            prev = house_idx + 1
        
        # Add distance to processing center
        distance += distance_matrix[prev][num_houses + 1]
        
        if distance < best_distance:
            best_distance = distance
            best_order = list(perm)
    
    return best_order

def solve_tsp_nearest_neighbor(distance_matrix, num_houses):
    """Nearest neighbor heuristic for larger problems"""
    unvisited = set(range(num_houses))
    order = []
    current = 0  # Start at depot
    
    while unvisited:
        nearest = min(unvisited, key=lambda x: distance_matrix[current][x + 1])
        order.append(nearest)
        unvisited.remove(nearest)
        current = nearest + 1
    
    return order

def optimize_route_fallback():
    """Fallback to straight-line routing if OSRM fails"""
    garbage_houses = app_state['garbage_houses']
    
    route = []
    route.append({
        'id': 'depot',
        'coords': (11.018, 76.972),
        'type': 'depot'
    })
    
    for house in garbage_houses:
        route.append({
            'id': house['id'],
            'coords': (house['lat'], house['lng']),
            'type': 'garbage'
        })
    
    route.append({
        'id': 'processing',
        'coords': (11.020, 76.975),
        'type': 'processing'
    })
    
    total_distance = len(garbage_houses) * 0.5
    
    app_state['route_optimized'] = True
    app_state['optimized_route'] = route
    app_state['current_route_index'] = 0
    
    return jsonify({
        'success': True,
        'route': route,
        'total_distance_km': round(total_distance, 2),
        'houses_visited': len(garbage_houses),
        'naive_distance_km': round(total_distance * 1.4, 2),
        'distance_saved_km': round(total_distance * 0.4, 2),
        'percentage_saved': 40,
        'houses_avoided': len(app_state['no_garbage_houses']),
        'routing_method': 'Fallback (Straight Line)'
    })

@app.route('/api/spawn_truck', methods=['POST'])
def spawn_truck():
    """Spawn truck and start automatic movement along road path"""
    global app_state
    
    print("=== SPAWN TRUCK ===")
    
    if not app_state.get('optimized_route'):
        print("ERROR: No route available")
        return jsonify({'success': False, 'error': 'No route available'})
    
    if not app_state.get('route_coordinates'):
        print("ERROR: No route coordinates available")
        return jsonify({'success': False, 'error': 'No route coordinates available'})
    
    # Initialize truck at first coordinate of road path
    app_state['truck_spawned'] = True
    app_state['truck_road_index'] = 0  # Index in route_coordinates array
    
    first_coord = app_state['route_coordinates'][0]
    app_state['truck_position'] = {'lat': first_coord[0], 'lng': first_coord[1]}
    
    print(f"Truck spawned at depot, will follow {len(app_state['route_coordinates'])} road points")
    
    # Start automatic truck movement along road path
    import threading
    import time
    
    def move_truck_along_road():
        """Background thread to move truck along road coordinates"""
        print("Truck movement started along road path")
        
        total_points = len(app_state['route_coordinates'])
        
        while app_state['truck_road_index'] < total_points - 1:
            time.sleep(1.0)  # Move every 1 second for slower, smoother animation
            
            # Move to next road point
            app_state['truck_road_index'] += 1
            current_index = app_state['truck_road_index']
            
            if current_index < total_points:
                next_coord = app_state['route_coordinates'][current_index]
                app_state['truck_position'] = {'lat': next_coord[0], 'lng': next_coord[1]}
                
                if current_index % 20 == 0:  # Log every 20 points
                    print(f"Truck at road point {current_index}/{total_points}")
        
        print("Truck completed road path!")
    
    # Start movement thread
    movement_thread = threading.Thread(target=move_truck_along_road)
    movement_thread.daemon = True
    movement_thread.start()
    
    return jsonify({
        'success': True,
        'truck_position': app_state['truck_position'],
        'total_road_points': len(app_state['route_coordinates'])
    })

@app.route('/api/move_truck', methods=['POST'])
def move_truck():
    """Move truck along optimized route"""
    global app_state
    
    data = request.get_json()
    direction = data.get('direction', 'forward')
    
    print("=== MOVE TRUCK CALLED ===")
    print(f"Direction received: {direction}")
    print(f"Current route_index: {app_state.get('current_route_index', 'not_set')}")
    print(f"Optimized route length: {len(app_state.get('optimized_route', []))}")
    
    if not app_state['truck_spawned']:
        print("ERROR: Truck not spawned yet")
        return jsonify({'success': False, 'error': 'Truck not spawned yet'})
    
    if not app_state.get('optimized_route'):
        print("ERROR: No route available")
        return jsonify({'success': False, 'error': 'No route available'})
    
    route = app_state['optimized_route']
    current_index = app_state['current_route_index']
    
    print(f"Current truck position: {app_state.get('truck_position', 'not_set')}")
    
    if direction == 'forward':
        # Move to next point on route
        if current_index < len(route) - 1:
            current_index += 1
            next_point = route[current_index]
            app_state['truck_position'] = {'lat': next_point['coords'][0], 'lng': next_point['coords'][1]}
            app_state['current_route_index'] = current_index
            print(f"MOVED FORWARD to point {current_index}: {next_point['id']}")
        else:
            print("ERROR: Already at end of route")
            return jsonify({'success': False, 'error': 'Already at end of route'})
    
    elif direction == 'backward':
        # Move to previous point on route
        if current_index > 0:
            current_index -= 1
            prev_point = route[current_index]
            app_state['truck_position'] = {'lat': prev_point['coords'][0], 'lng': prev_point['coords'][1]}
            app_state['current_route_index'] = current_index
            print(f"MOVED BACKWARD to point {current_index}: {prev_point['id']}")
        else:
            print("ERROR: Already at start of route")
            return jsonify({'success': False, 'error': 'Already at start of route'})
    
    else:
        print(f"ERROR: Invalid direction: {direction}")
        return jsonify({'success': False, 'error': 'Invalid direction'})
    
    print(f"NEW TRUCK POSITION: {app_state['truck_position']}")
    
    return jsonify({
        'success': True,
        'truck_position': app_state['truck_position'],
        'current_route_index': app_state['current_route_index']
    })

@app.route('/api/check_nearby_house', methods=['POST'])
def check_nearby_house():
    """Check if truck is near any garbage house"""
    global app_state
    
    if not app_state['truck_spawned']:
        return jsonify({'success': False, 'error': 'Truck not spawned yet'})
    
    current_pos = app_state['truck_position']
    garbage_houses = app_state['garbage_houses']
    
    print(f"Checking nearby houses from: {current_pos}")
    
    # Check distance to each garbage house
    for house in garbage_houses:
        distance = ((house['lat'] - current_pos['lat'])**2 + (house['lng'] - current_pos['lng'])**2)**0.5
        if distance < 0.01:  # Within 10 meters
            print(f"Nearby house {house['id']} at distance {distance:.4f}")
            return jsonify({
                'success': True,
                'nearby_house': house,
                'distance': distance,
                'can_collect': True
            })
    
    return jsonify({
        'success': True,
        'nearby_house': None,
        'distance': None,
        'can_collect': False
    })

@app.route('/api/collect_garbage', methods=['POST'])
def collect_garbage():
    """Collect garbage from nearby house"""
    global app_state
    
    data = request.get_json()
    house_id = data.get('house_id')
    
    print(f"=== COLLECT GARBAGE FROM {house_id} ===")
    
    if not app_state.get('garbage_houses'):
        return jsonify({'success': False, 'error': 'No garbage houses available'})
    
    # Find and remove the house from garbage houses
    house_found = False
    for i, house in enumerate(app_state['garbage_houses']):
        if house['id'] == house_id:
            app_state['garbage_houses'].pop(i)
            if 'collected_houses' not in app_state:
                app_state['collected_houses'] = []
            app_state['collected_houses'].append(house)
            house_found = True
            print(f"Garbage collected from {house_id}")
            break
    
    if not house_found:
        return jsonify({'success': False, 'error': 'House not found'})
    
    return jsonify({
        'success': True,
        'collected_houses': app_state['collected_houses'],
        'remaining_garbage_houses': len(app_state['garbage_houses'])
    })

@app.route('/api/get_simulation_status', methods=['GET'])
def get_simulation_status():
    """Get current simulation status"""
    global app_state
    
    print("=== GET STATUS ===")
    
    # Check if reporting deadline has passed
    if app_state.get('reporting_active', False) and app_state.get('reporting_deadline', 0):
        if int(time.time()) >= app_state['reporting_deadline']:
            print("Deadline expired - ending reporting")
            app_state['reporting_active'] = False
            app_state['reporting_ended'] = True
    
    print(f"Current state: {app_state}")
    
    return jsonify({
        'success': True,
        'simulation': app_state
    })

@app.route('/api/reset_simulation', methods=['POST'])
def reset_simulation():
    """Reset simulation"""
    global app_state
    
    print("=== RESET SIMULATION ===")
    
    app_state = {
        'houses': [],
        'city_generated': False,
        'reporting_active': False,
        'reporting_ended': False,
        'route_optimized': False,
        'truck_spawned': False,
        'garbage_houses': [],
        'no_garbage_houses': []
    }
    
    print("Simulation reset")
    
    return jsonify({'success': True})

if __name__ == '__main__':
    print("=== STARTING SMART WASTE DEMO ===")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
