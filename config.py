import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'developer-productivity-super-secret-key-2026')
    
    # SQLite Database URI (normalized forward-slash absolute path)
    db_file = os.path.join(basedir, 'instance', 'developer_productivity.db')
    # On Windows, sqlite absolute path requires 4 slashes: sqlite:///C:/...
    norm_path = os.path.abspath(db_file).replace('\\', '/')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{norm_path}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session and Cookie Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('FLASK_ENV') == 'production'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True

    # File Uploads
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'zip', 'py', 'js', 'json'}

    # Firebase Configuration
    FIREBASE_API_KEY = os.getenv('FIREBASE_API_KEY', '')
    FIREBASE_AUTH_DOMAIN = os.getenv('FIREBASE_AUTH_DOMAIN', 'developer-productivity-t-73574.firebaseapp.com')
    FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID', 'developer-productivity-t-73574')
    FIREBASE_STORAGE_BUCKET = os.getenv('FIREBASE_STORAGE_BUCKET', 'developer-productivity-t-73574.firebasestorage.app')
    FIREBASE_MESSAGING_SENDER_ID = os.getenv('FIREBASE_MESSAGING_SENDER_ID', '')
    FIREBASE_APP_ID = os.getenv('FIREBASE_APP_ID', '')
    FIREBASE_MEASUREMENT_ID = os.getenv('FIREBASE_MEASUREMENT_ID', '')
    FIREBASE_SERVICE_ACCOUNT_PATH = os.path.join(basedir, os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH', 'secrets/firebase-service-account.json'))

    # GitHub OAuth
    GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', '').strip().strip('"\'')
    GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', '').strip().strip('"\'')
    GITHUB_CALLBACK_URL = os.getenv('GITHUB_CALLBACK_URL', '').strip().strip('"\'')

    # xAI Grok API Configuration
    XAI_API_KEY = os.getenv('XAI_API_KEY', '').strip().strip('"\'')
    XAI_BASE_URL = os.getenv('XAI_BASE_URL', 'https://api.x.ai/v1').strip().strip('"\'')
    XAI_MODEL = os.getenv('XAI_MODEL', 'grok-4.7').strip().strip('"\'')

