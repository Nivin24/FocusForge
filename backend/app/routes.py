# backend/app/routes.py
import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from .rag.pipeline import FocusForgeRAG

api_bp = Blueprint('api', __name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Access user_rags via current_app — THIS IS THE CORRECT WAY
user_rags = property(lambda: current_app.user_rags)


@api_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    user_id = request.form.get('user_id') or request.args.get('user_id') or 'demo'

    if user_id not in user_rags:
        user_rags[user_id] = FocusForgeRAG(user_id)

    original_filename = secure_filename(file.filename)
    temp_path = os.path.join(UPLOAD_FOLDER, f"{user_id}_{uuid.uuid4()}_{original_filename}")
    file.save(temp_path)

    try:
        result = user_rags[user_id].add_or_replace_file(temp_path, original_filename)
        os.remove(temp_path)
        return jsonify({
            "message": result["message"],
            "filename": result["filename"],
            "uploaded_at": result["uploaded_at"],
            "chunks": result["chunks"],
            "action": result["action"]
        })
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500


@api_bp.route('/files', methods=['GET'])
def get_uploaded_files():
    user_id = request.args.get('user_id', 'demo')
    if user_id not in user_rags:
        user_rags[user_id] = FocusForgeRAG(user_id)
    files = user_rags[user_id].get_file_history()
    return jsonify({"files": files})


@api_bp.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json() or {}
        question = data.get('question', '').strip()
        mode = data.get('mode', 'study')
        user_id = data.get('user_id', 'demo')

        if not question:
            return jsonify({"answer": "Please type a question!", "sources": [], "used_web": False})

        if user_id not in user_rags:
            user_rags[user_id] = FocusForgeRAG(user_id=user_id)
            return jsonify({"answer": "No notes uploaded yet. Upload a PDF or text file first!", "sources": [], "used_web": False})

        result = user_rags[user_id].ask(question, mode=mode)
        if "not in notes yet" in result["answer"].lower():
            result["sources"] = []

        return jsonify(result)

    except Exception as e:
        print(f"Ask route error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"answer": "Sorry, something went wrong.", "sources": [], "used_web": False}), 500


@api_bp.route('/delete_file', methods=['POST'])
def delete_file():
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', 'demo')
        filename = data.get('filename')

        if not filename:
            return jsonify({"error": "Filename required"}), 400

        if user_id not in user_rags:
            user_rags[user_id] = FocusForgeRAG(user_id=user_id)

        result = user_rags[user_id].collection.get(where={"source": filename}, include=["metadatas"])
        ids_to_delete = result.get("ids", [])
        if ids_to_delete:
            user_rags[user_id].collection.delete(ids=ids_to_delete)
            return jsonify({"success": True, "message": "File deleted"}), 200

        return jsonify({"message": "File not found"}), 404

    except Exception as e:
        print(f"DELETE ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500