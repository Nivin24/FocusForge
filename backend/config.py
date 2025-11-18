import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "default-secret")
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")