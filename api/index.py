import os
import sys

# Add error handling for imports
try:
    from app import app
    print("✅ Flask app imported successfully")
except Exception as e:
    print(f"❌ Error importing Flask app: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    # Re-raise to prevent silent failures
    raise

# WSGI entry point for gunicorn
# Cloud Run will call: gunicorn index:app

if __name__ == "__main__":
    # Only for local development
    port = int(os.getenv("PORT", 8080))
    debug_mode = os.getenv("FLASK_ENV") == "development"
    
    print(f"🚀 Starting development server on port {port}")
    print(f"🐛 Debug mode: {debug_mode}")
    
    # Initialize DB for local dev
    try:
        from app import ensure_db_initialized
        ensure_db_initialized()
    except Exception as e:
        print(f"⚠️ DB initialization failed (non-fatal): {e}")
    
    app.run(host="0.0.0.0", port=port, debug=debug_mode)