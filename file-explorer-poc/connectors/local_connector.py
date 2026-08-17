import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from .storage_connector import IStorageConnector
from config.config import StorageConfig

class LocalConnector(IStorageConnector):
    """Implementation of IStorageConnector for local file system."""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.root_dir = config.root_dir

    async def connect(self) -> bool:
        """Verify the root directory exists."""
        print("[LocalConnector] connect() called.")
        if not self.root_dir.exists():
            self.root_dir.mkdir(parents=True, exist_ok=True)
        return True

    async def disconnect(self) -> bool:
        """Local filesystem doesn't require disconnection."""
        print("[LocalConnector] disconnect() called.")
        return True

    def _get_absolute_path(self, relative_path: str) -> Path:
        """Resolve a path relative to the root directory safely."""
        # Prevent directory traversal attacks
        target_path = (self.root_dir / relative_path).resolve()
        if not str(target_path).startswith(str(self.root_dir.resolve())):
            raise ValueError("Access denied: path traversal attempt")
        return target_path

    async def list_folders(self, path: str = "") -> List[str]:
        """Return all directories under the given path."""
        print(f"[LocalConnector] list_folders() called with path: '{path}'")
        target = self._get_absolute_path(path)
        if not target.is_dir():
            raise FileNotFoundError("Directory not found")

        return [item.name for item in target.iterdir() if item.is_dir()]

    async def list_files(self, path: str = "") -> List[Dict[str, Any]]:
        """Return files inside the selected directory."""
        print(f"[LocalConnector] list_files() called with path: '{path}'")
        target = self._get_absolute_path(path)
        if not target.is_dir():
            raise FileNotFoundError("Directory not found")

        files = []
        for item in target.iterdir():
            if item.is_file():
                files.append({
                    "name": item.name,
                    "size": item.stat().st_size,
                    "type": item.suffix.lstrip(".") or "unknown"
                })
        return files

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        """Return metadata for a specific file."""
        print(f"[LocalConnector] get_metadata() called with path: '{path}'")
        target = self._get_absolute_path(path)
        if not target.is_file():
            raise FileNotFoundError("File not found")

        stat = target.stat()
        return {
            "filename": target.name,
            "extension": target.suffix.lstrip(".") or "unknown",
            "size": stat.st_size,
            "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat()
        }

    async def read_file(self, path: str) -> str:
        """Return the text content of a file."""
        print(f"[LocalConnector] read_file() called with path: '{path}'")
        target = self._get_absolute_path(path)
        if not target.is_file():
            raise FileNotFoundError("File not found")

        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"[Unsupported File Type] This file appears to be a binary file and cannot be displayed as text. File size: {target.stat().st_size} bytes."

    async def download_file(self, path: str, destination: str) -> bool:
        """Copy a file to a specific destination path."""
        print(f"[LocalConnector] download_file() called with path: '{path}', destination: '{destination}'")
        target = self._get_absolute_path(path)
        if not target.is_file():
            raise FileNotFoundError("File not found")
        
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, dest_path)
        return True
