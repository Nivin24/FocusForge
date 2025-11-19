from flask import Flask
from flask_cors import CORS
import os

# GLOBAL USER CACHE — MUST BE HERE
user_rags = {}

from .routes import api_bp

def create_app():
    app = Flask(__name__, static_folder='../../frontend/dist', static_url_path='/')
    app.config.from_object('config.Config')

    # Super-strict CORS for dev
    CORS(
        app,
        resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}},
        supports_credentials=True,
        expose_headers=["Content-Type", "Authorization"]
    )

    # Global error handler — shows real crashes
    @app.errorhandler(Exception)
    def handle_error(e):
        app.logger.error(f"Uncaught exception: {e}")
        return {"error": "Internal server error", "details": str(e)}, 500

    # Register blueprint (this triggers user_rags creation)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Serve React
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path):
        if path and os.path.exists(os.path.join(app.static_folder or '', path)):
            return app.send_static_file(path)
        return app.send_static_file('index.html')

    return app