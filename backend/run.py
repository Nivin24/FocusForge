# backend/run.py   ← FINAL 100% WORKING VERSION FOR RENDER

from app import create_app
import os

# Global user cache
user_rags = {}

# Create the app
app = create_app()

if os.environ.get("RENDER") == "true":
    # Render environment
    port = int(os.environ.get("PORT", 10000))
    # No app.run() — Gunicorn handles it
    print(f"FocusForge API starting on Render port {port}")
else:
    # Local development only
    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000, debug=True)