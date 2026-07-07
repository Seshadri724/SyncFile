import shutil
from app.transfer.base import TransferEngine
from app.transfer.local import LocalTransferEngine
from app.transfer.rclone import RcloneTransferEngine
from app.config import settings

def get_transfer_engine() -> TransferEngine:
    # Use LocalTransferEngine by default for ease of testing/setup.
    # If settings.RCLONE_PATH is specified and available in the environment,
    # we can use RcloneTransferEngine.
    if settings.RCLONE_PATH != "rclone" and shutil.which(settings.RCLONE_PATH):
         return RcloneTransferEngine()
    return LocalTransferEngine()
