# backend/app/config.py
import os
from dotenv import load_dotenv

# Load .env file from project root (one level above backend/)
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '..', '.env')
load_dotenv(dotenv_path=env_path)

class Config:
    """Flask app configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY') or 'dev-secret-change-in-production'
    
    # LLM & Search APIs
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')  
    
    # Upload settings
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max file size
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'md'}

    # Chroma DB path
    CHROMA_DB_PATH = os.path.join(basedir, 'chroma_db')

    @staticmethod
    def init_app(app):
        # Create required directories
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.CHROMA_DB_PATH, exist_ok=True)