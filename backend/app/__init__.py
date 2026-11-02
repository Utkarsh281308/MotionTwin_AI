from pathlib import Path

from dotenv import load_dotenv

# Load secrets (e.g. META_API_KEY) from backend/.env before any module reads them.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
