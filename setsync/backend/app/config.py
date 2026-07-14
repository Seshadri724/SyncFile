import os
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./setsync.db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    API_TOKEN: str = "setsync_secret_token_123"
    
    # Pluggable Storage settings
    STORAGE_BACKEND: str = "local"
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "setsync-staging"
    R2_ENDPOINT_URL: str = ""
    
    # Per-tenant staging storage quota in bytes (Default: 5 GB)
    TENANT_STORAGE_QUOTA_BYTES: int = 5 * 1024 * 1024 * 1024
    
    # Cryptographic JWT Settings
    JWT_SECRET_KEY: str = "setsync_jwt_super_secret_key_change_me_in_prod"
    JWT_ALGORITHM: str = "HS256"
    
    # Request Rate Limiting (Default: 150 requests per 60 seconds sliding window)
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_MAX_REQUESTS: int = 150
    
    # Root scan directories for PC-A and PC-B when simulated locally
    PC_A_ROOT: str = str(Path("./test_pc_a").absolute())
    PC_B_ROOT: str = str(Path("./test_pc_b").absolute())
    
    # Directory to keep overwritten/deleted files for undo logic
    TRASH_DIR: str = str(Path("./.setsync_trash").absolute())
    UNDO_RETENTION_DAYS: int = 7
    UNDO_RETENTION_COUNT: int = 100
    
    # rclone path and settings
    RCLONE_PATH: str = "rclone"
    
    # CORS allowed origins
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    
    # Ops Maturity & Telemetry
    SENTRY_DSN: str = ""
    ENVIRONMENT: str = "development"
    LOG_FORMAT: str = "json"
    
    class Config:
        env_file = ".env"

settings = Settings()

# Ensure directories exist
os.makedirs(settings.PC_A_ROOT, exist_ok=True)
os.makedirs(settings.PC_B_ROOT, exist_ok=True)
os.makedirs(settings.TRASH_DIR, exist_ok=True)
