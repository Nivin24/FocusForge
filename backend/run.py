# backend/run.py
from app import create_app
import os

# Global user cache
user_rags = {}
app = create_app()

# THIS IS THE MAGIC THAT RENDER LOVES
# Gunicorn imports this file → we bind immediately
if os.environ.get("RENDER"):
    # Render environment
    import gunicorn.app.wsgiapp
    import sys
    port = int(os.environ.get("PORT", 10000))
    sys.argv = ["gunicorn", f"--bind=0.0.0.0:{port}", "run:app"]
    gunicorn.app.wsgiapp.run()
else:
    # Local development only
    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000, debug=True)