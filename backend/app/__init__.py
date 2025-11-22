# backend/app/__init__.py
from flask import Flask, jsonify
from flask_cors import CORS

# Import routes
from .routes import api_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Attach user_rags from run.py (correct way)
    from run import user_rags
    app.user_rags = user_rags

    # CORS — Allow Vercel frontend
    CORS(
        app,
        resources={r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "https://focusforgeai.vercel.app"
            ],
            "supports_credentials": True
        }}
    )

    # Register API routes
    app.register_blueprint(api_bp, url_prefix='/api')

    # CLEAN HOME PAGE — ONLY FOR API
    @app.route('/', methods=['GET'])
    def home():
        return jsonify({
            "message": "FocusForge API is LIVE",
            "version": "1.0",
            "active_users": len(user_rags),
            "frontend": "https://focusforgeai.vercel.app",
            "docs": "This is backend API only"
        })

    @app.route('/health')
    def health():
        return jsonify({
            "status": "healthy",
            "users_online": len(user_rags)
        })

    # Global error handler
    @app.errorhandler(Exception)
    def handle_error(e):
        app.logger.error(f"Server Error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    return app