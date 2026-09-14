import os
from smart_waste_demo import app

if __name__ == "__main__":
    from waitress import serve
    
    host = os.environ.get('HOST', '0.0.0.0')
    try:
        port = int(os.environ.get('PORT', 5000))
    except ValueError:
        port = 5000
        
    print(f"=== STARTING PRODUCTION WSGI SERVER ===")
    print(f"Server URL:  http://{host}:{port}")
    serve(app, host=host, port=port)
