import os
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent
class Config:
    SECRET_KEY=os.environ.get("SECRET_KEY","change-this-secret-key-before-production")
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL",f"sqlite:///{BASE_DIR/'instance'/'farm.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS=False
