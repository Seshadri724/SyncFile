import os
from pathlib import Path
from dotenv import load_dotenv

# Load agent-specific environment variables if they exist
load_dotenv(Path(__file__).parent / ".env")

CORE_SERVICE_URL = os.getenv("CORE_SERVICE_URL", "http://localhost:8000")
API_TOKEN = os.getenv("API_TOKEN", "setsync_secret_token_123")
PC_ID = os.getenv("PC_ID", "A") # Default to PC-A
AGENT_DB_PATH = os.getenv("AGENT_DB_PATH", "./agent_cache.db")
