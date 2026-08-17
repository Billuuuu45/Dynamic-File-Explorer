from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from config.config import StorageConfig

class IStorageConnector(ABC):
    """Abstract interface for all storage connectors."""

    def __init__(self, config: StorageConfig):
        self.config = config

    @abstractmethod
    async def connect(self) -> bool:
        """Establish a connection to the storage source."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Close the connection to the storage source."""
        pass

    @abstractmethod
    async def list_folders(self, path: str = "") -> List[str]:
        """List folders in a given path relative to root."""
        pass

    @abstractmethod
    async def list_files(self, path: str = "") -> List[Dict[str, Any]]:
        """List files in a given path relative to root."""
        pass

    @abstractmethod
    async def get_metadata(self, path: str) -> Dict[str, Any]:
        """Get metadata for a specific file."""
        pass

    @abstractmethod
    async def read_file(self, path: str) -> str:
        """Read text content of a specific file."""
        pass

    @abstractmethod
    async def download_file(self, path: str, destination: str) -> bool:
        """Download a file from storage to a local destination."""
        pass
