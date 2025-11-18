# backend/app/routes.py
import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from .rag.pipeline import FocusForgeRAG

api_bp = Blueprint('api', __name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global dict to hold user sessions
user_rags = {}

@api_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    user_id = request.args.get('user_id') or (request.get_json(silent=True) or {}).get('user_id', 'demo')

    # Initialize user session if not exists
    if user_id not in user_rags:
        user_rags[user_id] = FocusForgeRAG(user_id)

    original_filename = secure_filename(file.filename)
    temp_path = os.path.join(UPLOAD_FOLDER, f"{user_id}_{uuid.uuid4()}_{original_filename}")
    file.save(temp_path)

    try:
        # This now replaces duplicate + returns metadata
        result = user_rags[user_id].add_or_replace_file(temp_path, original_filename)
        os.remove(temp_path)

        return jsonify({
            "message": result["message"],
            "filename": result["filename"],
            "uploaded_at": result["uploaded_at"],
            "chunks": result["chunks"],
            "action": result["action"]  # "added" or "replaced"
        })

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500


@api_bp.route('/files', methods=['GET'])
def get_uploaded_files():
    """Return list of uploaded files with latest upload time (for sidebar)"""
    user_id = request.args.get('user_id') or (request.get_json(silent=True) or {}).get('user_id', 'demo')

    if user_id not in user_rags:
        user_rags[user_id] = FocusForgeRAG(user_id)

    files = user_rags[user_id].get_file_history()
    return jsonify({"files": files})


@api_bp.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json() or {}
        question = data.get('question', '').strip()
        user_id = request.args.get('user_id') or (request.get_json(silent=True) or {}).get('user_id', 'demo')

        if not question:
            return jsonify({"answer": "Please type a question!", "sources": [], "used_web": False})

        if user_id not in user_rags:
            user_rags[user_id] = FocusForgeRAG(user_id)
            return jsonify({
                "answer": "No notes uploaded yet. Upload a PDF or text file first!",
                "sources": [],
                "used_web": False
            })

        result = user_rags[user_id].ask(question)
        return jsonify(result)

    except Exception as e:
        print(f"Ask route error: {e}")
        return jsonify({
            "answer": "Sorry, something went wrong. Please try again.",
            "sources": [],
            "used_web": False
        }), 500