import os
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./setsync.db"
    API_TOKEN: str = "setsync_secret_token_123"
    
    # Root scan directories for PC-A and PC-B when simulated locally
    PC_A_ROOT: str = str(Path("./test_pc_a").absolute())
    PC_B_ROOT: str = str(Path("./test_pc_b").absolute())
    
    # Directory to keep overwritten/deleted files for undo logic
    TRASH_DIR: str = str(Path("./.setsync_trash").absolute())
    UNDO_RETENTION_DAYS: int = 7
    UNDO_RETENTION_COUNT: int = 100
    
    # rclone path and settings
    RCLONE_PATH: str = "rclone"
    
    class Config:
        env_file = ".env"

settings = Settings()

# Ensure directories exist
os.makedirs(settings.PC_A_ROOT, exist_ok=True)
os.makedirs(settings.PC_B_ROOT, exist_ok=True)
os.makedirs(settings.TRASH_DIR, exist_ok=True)
