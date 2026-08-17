import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Base configuration
BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR / "sample-files"

@dataclass
class StorageConfig:
    """Configuration class to pass down to Storage Connectors."""
    storage_type: str
    root_dir: Path
    # Future generic config options for enterprise storage:
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region: Optional[str] = None
    endpoint_url: Optional[str] = None
    bucket_name: Optional[str] = None
    share_name: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

# Global configuration instance
APP_CONFIG = StorageConfig(
    storage_type=os.getenv("CONNECTOR_TYPE", "local"),
    root_dir=ROOT_DIR,
    # These would be populated from env vars in a real app
    access_key=os.getenv("STORAGE_ACCESS_KEY"),
    secret_key=os.getenv("STORAGE_SECRET_KEY"),
)
