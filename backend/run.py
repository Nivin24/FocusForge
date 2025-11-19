from app import create_app
import os

# THIS IS THE FIX — GLOBAL USER CACHE FOR ALL USERS
user_rags = {}

app = create_app()

if __name__ == "__main__":
    env = os.getenv("FLASK_ENV", "development")
    debug = env == "development"
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", debug=debug, port=port)