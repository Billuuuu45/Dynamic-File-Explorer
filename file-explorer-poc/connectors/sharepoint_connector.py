import logging
import asyncio
from typing import List, Dict, Any
import requests
import msal

from .storage_connector import IStorageConnector
from config.config import StorageConfig

logger = logging.getLogger(__name__)

class SharePointConnector(IStorageConnector):
    """SharePoint / OneDrive integration via Microsoft Graph API."""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.tenant_id = self.config.tenant_id
        self.client_id = self.config.client_id
        self.client_secret = self.config.client_secret
        self.site_id = self.config.share_name
        self.access_token = None
        self.base_url = "https://graph.microsoft.com/v1.0"

    async def connect(self) -> bool:
        try:
            logger.info("[SharePointConnector] Connecting to SharePoint via MS Graph...")
            
            if not all([self.tenant_id, self.client_id, self.client_secret, self.site_id]):
                raise ValueError("Missing required config (tenant_id, client_id, client_secret, share_name) for SharePoint.")

            def _authenticate():
                authority = f"https://login.microsoftonline.com/{self.tenant_id}"
                app = msal.ConfidentialClientApplication(
                    self.client_id,
                    authority=authority,
                    client_credential=self.client_secret,
                )
                
                result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
                
                if "access_token" in result:
                    return result["access_token"]
                else:
                    error = result.get("error")
                    error_description = result.get("error_description")
                    raise PermissionError(f"Authentication failed: {error} - {error_description}")

            self.access_token = await asyncio.to_thread(_authenticate)
            
            # Test connection by fetching site details
            def _test_connection():
                headers = {"Authorization": f"Bearer {self.access_token}"}
                response = requests.get(f"{self.base_url}/sites/{self.site_id}", headers=headers)
                response.raise_for_status()
                
            await asyncio.to_thread(_test_connection)

            logger.info("[SharePointConnector] Connection successful.")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"[SharePointConnector] HTTP Error during connection: {e}")
            raise
        except Exception as e:
            logger.error(f"[SharePointConnector] Connection Failed: {e}")
            raise

    async def disconnect(self) -> bool:
        try:
            logger.info("[SharePointConnector] Disconnecting...")
            self.access_token = None
            logger.info("[SharePointConnector] Disconnected.")
            return True
        except Exception as e:
            logger.error(f"[SharePointConnector] Disconnect Error: {e}")
            raise

    def _get_headers(self):
        if not self.access_token:
            raise PermissionError("Not connected or missing access token.")
        return {"Authorization": f"Bearer {self.access_token}"}

    def _get_drive_url(self, path: str):
        clean_path = path.strip("/")
        if clean_path:
            return f"{self.base_url}/sites/{self.site_id}/drive/root:/{clean_path}:/children"
        else:
            return f"{self.base_url}/sites/{self.site_id}/drive/root/children"

    def _get_item_url(self, path: str):
        clean_path = path.strip("/")
        if clean_path:
            return f"{self.base_url}/sites/{self.site_id}/drive/root:/{clean_path}"
        else:
            return f"{self.base_url}/sites/{self.site_id}/drive/root"

    async def list_folders(self, path: str = "") -> List[str]:
        try:
            logger.info(f"[SharePointConnector] Listing folders in path: '{path}'")
            if not self.access_token:
                await self.connect()

            def _list_folders():
                url = self._get_drive_url(path)
                response = requests.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                
                folders = []
                for item in data.get("value", []):
                    if "folder" in item:
                        folders.append(item["name"])
                return folders

            return await asyncio.to_thread(_list_folders)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"[SharePointConnector] Folder not found: {path}")
                raise FileNotFoundError(f"Folder not found: {path}")
            logger.error(f"[SharePointConnector] HTTP Error listing folders: {e}")
            raise
        except Exception as e:
            logger.error(f"[SharePointConnector] Error listing folders: {e}")
            raise

    async def list_files(self, path: str = "") -> List[Dict[str, Any]]:
        try:
            logger.info(f"[SharePointConnector] Listing files in path: '{path}'")
            if not self.access_token:
                await self.connect()

            def _list_files():
                url = self._get_drive_url(path)
                response = requests.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                
                files = []
                for item in data.get("value", []):
                    if "file" in item:
                        file_name = item["name"]
                        extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""
                        files.append({
                            "name": file_name,
                            "path": f"{path.strip('/')}/{file_name}".strip('/'),
                            "size": item.get("size", 0),
                            "type": extension,
                            "modified": item.get("lastModifiedDateTime")
                        })
                return files

            return await asyncio.to_thread(_list_files)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"[SharePointConnector] Folder not found: {path}")
                raise FileNotFoundError(f"Folder not found: {path}")
            logger.error(f"[SharePointConnector] HTTP Error listing files: {e}")
            raise
        except Exception as e:
            logger.error(f"[SharePointConnector] Error listing files: {e}")
            raise

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        try:
            logger.info(f"[SharePointConnector] Getting metadata for path: '{path}'")
            if not self.access_token:
                await self.connect()

            def _get_metadata():
                url = self._get_item_url(path)
                response = requests.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                
                file_name = data.get("name", "")
                extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""

                return {
                    "name": file_name,
                    "extension": extension,
                    "size": data.get("size", 0),
                    "created": data.get("createdDateTime"),
                    "modified": data.get("lastModifiedDateTime"),
                    "storage": "SharePoint"
                }

            return await asyncio.to_thread(_get_metadata)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"[SharePointConnector] File Missing: {path}")
                raise FileNotFoundError(f"File not found: {path}")
            logger.error(f"[SharePointConnector] HTTP Error getting metadata: {e}")
            raise
        except Exception as e:
            logger.error(f"[SharePointConnector] Error getting metadata: {e}")
            raise

    async def read_file(self, path: str) -> str:
        try:
            logger.info(f"[SharePointConnector] Reading File: '{path}'")
            if not self.access_token:
                await self.connect()

            def _read_file():
                url = f"{self._get_item_url(path)}/content"
                response = requests.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.text

            return await asyncio.to_thread(_read_file)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"[SharePointConnector] File Missing: {path}")
                raise FileNotFoundError(f"File not found: {path}")
            logger.error(f"[SharePointConnector] HTTP Error reading file: {e}")
            raise
        except Exception as e:
            logger.error(f"[SharePointConnector] Error reading file: {e}")
            raise

    async def download_file(self, path: str, destination: str) -> bool:
        try:
            logger.info(f"[SharePointConnector] Downloading file '{path}' to '{destination}'")
            if not self.access_token:
                await self.connect()

            def _download_file():
                url = f"{self._get_item_url(path)}/content"
                response = requests.get(url, headers=self._get_headers(), stream=True)
                response.raise_for_status()
                
                with open(destination, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            await asyncio.to_thread(_download_file)
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"[SharePointConnector] File Missing: {path}")
                raise FileNotFoundError(f"File not found: {path}")
            logger.error(f"[SharePointConnector] HTTP Error downloading file: {e}")
            raise
        except Exception as e:
            logger.error(f"[SharePointConnector] Error downloading file: {e}")
            raise
