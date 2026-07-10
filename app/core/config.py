import os
from dotenv import load_dotenv
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# =========================
# Database
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# OpenAI
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# UPLOAD_DIR     = os.getenv("UPLOAD_DIR")
# BASE_URL       = os.getenv("BASE_URL")
#
# CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
# CLOUDINARY_API_KEY    = os.getenv("CLOUDINARY_API_KEY")
# CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
#
# if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
#     raise RuntimeError("Missing Cloudinary env variables")
#
# if not DATABASE_URL or not OPENAI_API_KEY:
#     raise RuntimeError("Missing env variables")
