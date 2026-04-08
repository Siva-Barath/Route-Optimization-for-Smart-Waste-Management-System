from flask import Flask, jsonify, request
import time

app = Flask(__name__)

app_state = {
    'houses': [
        {'id': 'B1', 'type': 'bin', 'status': 'EMPTY'},
        {'id': 'B2', 'type': 'bin', 'status': 'EMPTY'}
    ]
}

@app.route("/", methods=["GET"])
def home():
    return "IoT Test Server Running"

@app.route("/api/test", methods=["GET"])
def test():
    return jsonify({"message": "IoT server is working!", "timestamp": int(time.time())})

@app.route("/api/bin_status", methods=["POST"])
def update_bin_status():
    print("=== IOT REQUEST RECEIVED ===")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request data: {request.get_data()}")
    
    try:
        data = request.get_json()
        print(f"Parsed JSON: {data}")
        
        bin_id = data.get("bin_id")
        status = data.get("status")
        
        print(f"Bin ID: {bin_id}")
        print(f"Status: {status}")
        
        # Find and update bin status
        for location in app_state.get('houses', []):
            if location.get('type') == 'bin' and location.get('id') == bin_id:
                old_status = location.get('status')
                location['status'] = status
                print(f"✅ Bin {bin_id} changed from {old_status} to {status}")
                break
        
        return jsonify({"message": "success", "bin_id": bin_id, "status": status})
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("=== IOT SERVER STARTING ===")
    print("Server running on http://localhost:5000")
    print("Waiting for IoT bin updates...")
    app.run(debug=True, host='0.0.0.0', port=5000)
