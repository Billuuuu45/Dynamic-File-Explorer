import logging
import asyncio
from typing import List, Dict, Any
from google.cloud import storage
from google.cloud.exceptions import NotFound, Forbidden, GoogleCloudError
from google.oauth2 import service_account

from .storage_connector import IStorageConnector
from config.config import StorageConfig

logger = logging.getLogger(__name__)

class GCSConnector(IStorageConnector):
    """Google Cloud Storage integration."""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.client = None
        self.bucket_name = self.config.bucket_name
        self.bucket = None

    async def connect(self) -> bool:
        try:
            logger.info("[GCSConnector] Connecting to Google Cloud Storage...")
            
            if not self.bucket_name:
                raise ValueError("Bucket name is not configured for GCS.")

            def _connect():
                # For GCS, we assume access_key holds path to service account JSON,
                # or we fall back to default application credentials if empty
                if self.config.access_key:
                    credentials = service_account.Credentials.from_service_account_file(self.config.access_key)
                    client = storage.Client(credentials=credentials)
                else:
                    client = storage.Client()
                
                bucket = client.bucket(self.bucket_name)
                # Test connection
                if not bucket.exists():
                    raise FileNotFoundError(f"Bucket not found: {self.bucket_name}")
                return client, bucket

            self.client, self.bucket = await asyncio.to_thread(_connect)
            logger.info("[GCSConnector] Connection successful.")
            return True
        except NotFound as e:
            logger.error(f"[GCSConnector] Bucket Not Found: {e}")
            raise FileNotFoundError(f"Bucket not found: {self.bucket_name}")
        except Forbidden as e:
            logger.error(f"[GCSConnector] Permission Denied: {e}")
            raise PermissionError(f"Permission denied for bucket: {self.bucket_name}")
        except GoogleCloudError as e:
            logger.error(f"[GCSConnector] Connection Failed (GoogleCloudError): {e}")
            raise
        except Exception as e:
            logger.error(f"[GCSConnector] Unexpected Connection Error: {e}")
            raise

    async def disconnect(self) -> bool:
        try:
            logger.info("[GCSConnector] Disconnecting from GCS...")
            if self.client:
                def _disconnect():
                    self.client.close()
                await asyncio.to_thread(_disconnect)
                self.client = None
                self.bucket = None
            logger.info("[GCSConnector] Disconnected.")
            return True
        except Exception as e:
            logger.error(f"[GCSConnector] Disconnect Error: {e}")
            raise

    async def list_folders(self, path: str = "") -> List[str]:
        try:
            logger.info(f"[GCSConnector] Listing folders in path: '{path}'")
            if not self.client or not self.bucket:
                await self.connect()

            prefix = path if not path or path.endswith('/') else f"{path}/"
            if prefix == "/":
                prefix = ""

            def _list_folders():
                iterator = self.client.list_blobs(self.bucket, prefix=prefix, delimiter='/')
                # Iterate through to populate iterator.prefixes
                list(iterator)
                folders = []
                for p in iterator.prefixes:
                    folder_name = p[len(prefix):].strip('/')
                    if folder_name:
                        folders.append(folder_name)
                return folders

            return await asyncio.to_thread(_list_folders)
        except GoogleCloudError as e:
            logger.error(f"[GCSConnector] SDK Error listing folders: {e}")
            raise
        except Exception as e:
            logger.error(f"[GCSConnector] Error listing folders: {e}")
            raise

    async def list_files(self, path: str = "") -> List[Dict[str, Any]]:
        try:
            logger.info(f"[GCSConnector] Listing files in path: '{path}'")
            if not self.client or not self.bucket:
                await self.connect()

            prefix = path if not path or path.endswith('/') else f"{path}/"
            if prefix == "/":
                prefix = ""

            def _list_files():
                files = []
                iterator = self.client.list_blobs(self.bucket, prefix=prefix, delimiter='/')
                for blob in iterator:
                    if blob.name == prefix:
                        continue # Skip directory marker
                    
                    file_name = blob.name[len(prefix):]
                    extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""
                    
                    files.append({
                        "name": file_name,
                        "path": blob.name,
                        "size": blob.size,
                        "type": extension,
                        "modified": blob.updated.isoformat() if blob.updated else None
                    })
                return files

            return await asyncio.to_thread(_list_files)
        except GoogleCloudError as e:
            logger.error(f"[GCSConnector] SDK Error listing files: {e}")
            raise
        except Exception as e:
            logger.error(f"[GCSConnector] Error listing files: {e}")
            raise

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        try:
            logger.info(f"[GCSConnector] Getting metadata for path: '{path}'")
            if not self.client or not self.bucket:
                await self.connect()

            def _get_metadata():
                blob = self.bucket.get_blob(path)
                if not blob:
                    raise FileNotFoundError(f"File not found: {path}")

                file_name = path.split('/')[-1]
                extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""

                return {
                    "name": file_name,
                    "extension": extension,
                    "size": blob.size,
                    "created": blob.time_created.isoformat() if blob.time_created else None,
                    "modified": blob.updated.isoformat() if blob.updated else None,
                    "storage": "Google Cloud Storage"
                }

            return await asyncio.to_thread(_get_metadata)
        except FileNotFoundError as e:
            logger.error(f"[GCSConnector] File Missing: {path}")
            raise
        except GoogleCloudError as e:
            logger.error(f"[GCSConnector] SDK Error getting metadata: {e}")
            raise
        except Exception as e:
            logger.error(f"[GCSConnector] Unexpected Error: {e}")
            raise

    async def read_file(self, path: str) -> str:
        try:
            logger.info(f"[GCSConnector] Reading File: '{path}'")
            if not self.client or not self.bucket:
                await self.connect()

            def _read_file():
                blob = self.bucket.get_blob(path)
                if not blob:
                    raise FileNotFoundError(f"File not found: {path}")
                return blob.download_as_text()

            return await asyncio.to_thread(_read_file)
        except FileNotFoundError as e:
            logger.error(f"[GCSConnector] File Missing: {path}")
            raise
        except GoogleCloudError as e:
            logger.error(f"[GCSConnector] SDK Error reading file: {e}")
            raise
        except Exception as e:
            logger.error(f"[GCSConnector] Unexpected Error: {e}")
            raise

    async def download_file(self, path: str, destination: str) -> bool:
        try:
            logger.info(f"[GCSConnector] Downloading file '{path}' to '{destination}'")
            if not self.client or not self.bucket:
                await self.connect()

            def _download_file():
                blob = self.bucket.get_blob(path)
                if not blob:
                    raise FileNotFoundError(f"File not found: {path}")
                blob.download_to_filename(destination)

            await asyncio.to_thread(_download_file)
            return True
        except FileNotFoundError as e:
            logger.error(f"[GCSConnector] File Missing: {path}")
            raise
        except GoogleCloudError as e:
            logger.error(f"[GCSConnector] SDK Error downloading file: {e}")
            raise
        except Exception as e:
            logger.error(f"[GCSConnector] Unexpected Error: {e}")
            raise
