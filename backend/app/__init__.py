# backend/app/__init__.py
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os

# DO NOT IMPORT user_rags here — it's in run.py
from .routes import api_bp

def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object('config.Config')

    # Attach user_rags to app so routes can access it
    # This is the PROFESSIONAL Flask way
    from run import user_rags
    app.user_rags = user_rags

    # CORS — Allow your frontend
    CORS(
        app,
        resources={r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "https://focusforgeai.vercel.app",
                "https://focusforge-9pov.onrender.com"
            ],
            "supports_credentials": True
        }}
    )

    app.register_blueprint(api_bp, url_prefix='/api')

    # SERVE REACT APP
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path):
        if path.startswith('api/'):
            return jsonify({"error": "API route"}), 404

        dist_folder = os.path.join(app.root_path, '..', '..', 'frontend', 'dist')
        full_path = os.path.join(dist_folder, path)

        if path and os.path.exists(full_path) and os.path.isfile(full_path):
            return send_from_directory(dist_folder, path)

        return send_from_directory(dist_folder, 'index.html')

    @app.route('/health')
    def health():
        return jsonify({"status": "healthy", "active_users": len(user_rags)})

    @app.errorhandler(Exception)
    def handle_error(e):
        app.logger.error(f"Error: {e}", exc0_info=True)
        return jsonify({"error": "Server error"}), 500

    return app