import os
from app import app  # Import Flask app from app.py

# This is the WSGI entry point for gunicorn
# Gunicorn will call this as: gunicorn index:app

if __name__ == "__main__":
    # Only used for local development (python index.py)
    # Cloud Run uses gunicorn, so this block is ignored in production
    port = int(os.getenv("PORT", 8080))
    debug_mode = os.getenv("FLASK_ENV") == "development"
    
    print(f"🚀 Starting development server on port {port}")
    print(f"🐛 Debug mode: {debug_mode}")
    
    app.run(host="0.0.0.0", port=port, debug=debug_mode)