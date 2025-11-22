# backend/run.py
from app import create_app
import os

# GLOBAL USER CACHE — ONLY HERE
user_rags = {}

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)