# backend/app/__init__.py
from flask import Flask, jsonify, request
# from flask_cors import CORS
from .routes import api_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    from run import user_rags
    app.user_rags = user_rags

    # CORS — Allow Vercel frontend
    # CORS(
    #     app,
    #     resources={r"/api/*": {
    #         "origins": [
    #             "http://localhost:5173",
    #             "http://127.0.0.1:5173",
    #             "https://focusforgeai.vercel.app"
    #         ],
    #         "methods": ["GET", "POST", "OPTIONS", "DELETE"],
    #         "allow_headers": ["Content-Type", "Authorization"],
    #         "expose_headers": ["Content-Type", "X-Requested-With"],
    #         "supports_credentials": True,
    #         "max_age": 600
    #     }}
    # )
    # app.config['CORS_EXPOSE_HEADERS'] = 'Content-Type'
    
        # NUCLEAR CORS FIX — WORKS 100% ON RENDER EVEN AFTER CRASH/RESTART
    # Delete Flask-CORS completely — it fails silently on Render

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin')
        if origin in [
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'https://focusforgeai.vercel.app'
        ]:
            response.headers['Access-Control-Allow-Origin'] = origin
        else:
            response.headers['Access-Control-Allow-Origin'] = 'https://focusforgeai.vercel.app'

        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-Requested-With'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type'
        return response

    # Handle preflight requests
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = Flask.make_response(__name__)
            response.headers['Access-Control-Allow-Origin'] = 'https://focusforgeai.vercel.app'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-Requested-With'
            response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
            response.status_code = 200
            return response
    
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


    @app.route('/favicon.ico')
    def favicon():
        return '', 204  # No content → no error
    
    return app