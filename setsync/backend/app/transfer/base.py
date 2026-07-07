from abc import ABC, abstractmethod
from typing import Dict, Any

class TransferEngine(ABC):
    @abstractmethod
    async def copy(self, src: str, dest: str) -> None:
        """Copy a file from src absolute path to dest absolute path."""
        pass

    @abstractmethod
    async def move(self, src: str, dest: str) -> None:
        """Move a file from src absolute path to dest absolute path."""
        pass

    @abstractmethod
    async def dry_run(self, src: str, dest: str, action_type: str) -> Dict[str, Any]:
        """Perform dry run, checking if destination exists and metadata comparisons."""
        pass
