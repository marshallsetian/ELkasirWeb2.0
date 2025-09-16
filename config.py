import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
USER_DB_FOLDER = os.path.join(BASE_DIR, "users_db")
os.makedirs(USER_DB_FOLDER, exist_ok=True)

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "default_secret_key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'main_user.db')}"
