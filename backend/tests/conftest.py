import os
import sys
from pathlib import Path

# Tests never call the paid Meta API (load_dotenv won't override an existing variable).
os.environ["META_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
