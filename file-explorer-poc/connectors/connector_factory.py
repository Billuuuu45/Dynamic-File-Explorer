from config.config import APP_CONFIG
from .storage_connector import IStorageConnector
from .local_connector import LocalConnector
from .s3_connector import S3Connector
from .azure_blob_connector import AzureBlobConnector
from .gcs_connector import GCSConnector
from .smb_connector import SMBConnector
from .sharepoint_connector import SharePointConnector
from .google_drive_connector import GoogleDriveConnector

def get_connector() -> IStorageConnector:
    """Factory method to get the configured storage connector implementation."""
    storage_type = APP_CONFIG.storage_type.lower()
    
    match storage_type:
        case "local":
            return LocalConnector(APP_CONFIG)
        case "s3":
            return S3Connector(APP_CONFIG)
        case "azure":
            return AzureBlobConnector(APP_CONFIG)
        case "gcs":
            return GCSConnector(APP_CONFIG)
        case "smb":
            return SMBConnector(APP_CONFIG)
        case "sharepoint":
            return SharePointConnector(APP_CONFIG)
        case "gdrive":
            return GoogleDriveConnector(APP_CONFIG)
        case _:
            raise ValueError(f"Unsupported storage type: {storage_type}")
