import logging
import datetime
from typing import List, Dict, Any
from azure.storage.blob.aio import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

from .storage_connector import IStorageConnector
from config.config import StorageConfig

logger = logging.getLogger(__name__)

class AzureBlobConnector(IStorageConnector):
    """Azure Blob Storage integration."""
    
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.blob_service_client = None
        self.container_client = None
        self.container_name = self.config.bucket_name or "default-container"

    async def connect(self) -> bool:
        try:
            logger.info("[AzureBlobConnector] Connecting to Azure Blob Storage...")
            
            connection_string = self.config.access_key
            
            if connection_string and "DefaultEndpointsProtocol" in connection_string:
                self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            elif self.config.endpoint_url:
                self.blob_service_client = BlobServiceClient(
                    account_url=self.config.endpoint_url,
                    credential=self.config.access_key
                )
            else:
                raise ValueError("Valid connection string or endpoint URL not provided.")

            self.container_client = self.blob_service_client.get_container_client(self.container_name)
            
            # Test connection
            if not await self.container_client.exists():
                logger.warning(f"[AzureBlobConnector] Container '{self.container_name}' does not exist.")
            
            logger.info("[AzureBlobConnector] Connection successful.")
            return True
        except HttpResponseError as e:
            logger.error(f"[AzureBlobConnector] Connection Failed (HttpResponseError): {e}")
            raise
        except Exception as e:
            logger.error(f"[AzureBlobConnector] Connection Failed: {e}")
            raise

    async def disconnect(self) -> bool:
        try:
            logger.info("[AzureBlobConnector] Disconnecting...")
            if self.blob_service_client:
                await self.blob_service_client.close()
                self.blob_service_client = None
                self.container_client = None
            logger.info("[AzureBlobConnector] Disconnected.")
            return True
        except Exception as e:
            logger.error(f"[AzureBlobConnector] Disconnect Error: {e}")
            raise

    async def list_folders(self, path: str = "") -> List[str]:
        try:
            logger.info(f"[AzureBlobConnector] Listing folders in path: '{path}'")
            if not self.container_client:
                await self.connect()
                
            if not await self.container_client.exists():
                raise FileNotFoundError(f"Container not found: {self.container_name}")

            prefix = path if not path or path.endswith('/') else f"{path}/"
            if prefix == "/":
                prefix = ""

            folders = []
            
            async for blob in self.container_client.walk_blobs(name_starts_with=prefix):
                if blob.name.endswith('/'):
                    folder_name = blob.name[len(prefix):].strip('/')
                    if folder_name and folder_name not in folders:
                        folders.append(folder_name)
            
            return folders
        except ResourceNotFoundError as e:
            logger.error(f"[AzureBlobConnector] Resource not found: {e}")
            raise FileNotFoundError(f"Resource not found: {path}")
        except Exception as e:
            logger.error(f"[AzureBlobConnector] Error listing folders: {e}")
            raise

    async def list_files(self, path: str = "") -> List[Dict[str, Any]]:
        try:
            logger.info(f"[AzureBlobConnector] Listing files in path: '{path}'")
            if not self.container_client:
                await self.connect()

            if not await self.container_client.exists():
                raise FileNotFoundError(f"Container not found: {self.container_name}")

            prefix = path if not path or path.endswith('/') else f"{path}/"
            if prefix == "/":
                prefix = ""

            files = []
            
            async for blob in self.container_client.walk_blobs(name_starts_with=prefix):
                if not blob.name.endswith('/'):
                    file_name = blob.name[len(prefix):]
                    extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""
                    
                    modified = blob.last_modified
                    if isinstance(modified, datetime.datetime):
                        modified = modified.isoformat()

                    files.append({
                        "name": file_name,
                        "path": blob.name,
                        "size": blob.size,
                        "type": extension,
                        "modified": modified
                    })
            
            return files
        except ResourceNotFoundError as e:
            logger.error(f"[AzureBlobConnector] Resource not found: {e}")
            raise FileNotFoundError(f"Resource not found: {path}")
        except Exception as e:
            logger.error(f"[AzureBlobConnector] Error listing files: {e}")
            raise

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        try:
            logger.info(f"[AzureBlobConnector] Getting metadata for path: '{path}'")
            if not self.container_client:
                await self.connect()

            blob_client = self.container_client.get_blob_client(path)
            if not await blob_client.exists():
                raise FileNotFoundError(f"File not found: {path}")

            properties = await blob_client.get_blob_properties()
            
            file_name = path.split('/')[-1]
            extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""

            modified = properties.last_modified
            if isinstance(modified, datetime.datetime):
                modified = modified.isoformat()
            
            created = properties.creation_time
            if isinstance(created, datetime.datetime):
                created = created.isoformat()

            return {
                "name": file_name,
                "extension": extension,
                "size": properties.size,
                "created": created or modified,
                "modified": modified,
                "storage": "Azure Blob Storage"
            }
        except ResourceNotFoundError as e:
            logger.error(f"[AzureBlobConnector] File Missing: {path}")
            raise FileNotFoundError(f"File not found: {path}")
        except Exception as e:
            logger.error(f"[AzureBlobConnector] SDK Error: {e}")
            raise

    async def read_file(self, path: str) -> str:
        try:
            logger.info(f"[AzureBlobConnector] Reading File: '{path}'")
            if not self.container_client:
                await self.connect()

            blob_client = self.container_client.get_blob_client(path)
            if not await blob_client.exists():
                raise FileNotFoundError(f"File not found: {path}")

            downloader = await blob_client.download_blob()
            content_bytes = await downloader.readall()
            return content_bytes.decode('utf-8')
        except ResourceNotFoundError as e:
            logger.error(f"[AzureBlobConnector] File Missing: {path}")
            raise FileNotFoundError(f"File not found: {path}")
        except Exception as e:
            logger.error(f"[AzureBlobConnector] SDK Error: {e}")
            raise

    async def download_file(self, path: str, destination: str) -> bool:
        try:
            logger.info(f"[AzureBlobConnector] Downloading file '{path}' to '{destination}'")
            if not self.container_client:
                await self.connect()

            blob_client = self.container_client.get_blob_client(path)
            if not await blob_client.exists():
                raise FileNotFoundError(f"File not found: {path}")

            downloader = await blob_client.download_blob()
            content_bytes = await downloader.readall()
            with open(destination, "wb") as file:
                file.write(content_bytes)
            return True
        except ResourceNotFoundError as e:
            logger.error(f"[AzureBlobConnector] File Missing: {path}")
            raise FileNotFoundError(f"File not found: {path}")
        except Exception as e:
            logger.error(f"[AzureBlobConnector] SDK Error: {e}")
            raise
