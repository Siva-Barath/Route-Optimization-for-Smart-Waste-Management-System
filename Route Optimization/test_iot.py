from flask import Flask, jsonify, request

app = Flask(__name__)

app_state = {
    'houses': [
        {'id': 'B1', 'type': 'bin', 'status': 'EMPTY'},
        {'id': 'B2', 'type': 'bin', 'status': 'EMPTY'}
    ]
}

@app.route("/api/bin_status", methods=["POST"])
def update_bin_status():
    data = request.get_json()
    
    print("🚨 BIN UPDATE RECEIVED:", data)
    
    bin_id = data.get("bin_id")
    status = data.get("status")
    
    # Find and update bin status
    for location in app_state.get('houses', []):
        if location.get('type') == 'bin' and location.get('id') == bin_id:
            location['status'] = status
            print(f"✅ Bin {bin_id} updated to {status}")
            break
    
    return {"message": "success"}

if __name__ == '__main__':
    print("=== TESTING IOT BIN UPDATE ===")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
