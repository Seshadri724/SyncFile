import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

AGENT_DB_PATH = os.getenv("AGENT_DB_PATH", "./agent_cache.db")

def get_agent_config(key: str, default: str = "") -> str:
    """Helper to retrieve configuration value from agent database config table first, falling back to environment variables."""
    if key in ["tenant_key", "agent_key", "api_token"]:
        try:
            import keyring
            val = keyring.get_password("setsync", key)
            if val is not None:
                return val
        except Exception:
            pass
            
    try:
        from agent.db import get_config
        val = get_config(key)
        if val is not None:
            return val
    except Exception:
        pass
    
    # Environment fallbacks
    env_mapping = {
        "core_url": "CORE_SERVICE_URL",
        "api_token": "API_TOKEN",
        "source_id": "SOURCE_ID",
        "agent_key": "AGENT_KEY",
        "tenant_key": "TENANT_KEY",
        "roots": "ROOT_PATHS"
    }
    env_key = env_mapping.get(key, key.upper())
    return os.getenv(env_key, default)
