import logging
import asyncio
import io
from typing import List, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from .storage_connector import IStorageConnector
from config.config import StorageConfig

logger = logging.getLogger(__name__)

class GoogleDriveConnector(IStorageConnector):
    """Google Drive integration via Google Drive API v3."""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.service = None
        self.credentials_path = self.config.access_key
        # We assume path represents 'id' or we navigate by name.
        # For simplicity in this interface, we'll treat `path` as a folder ID 
        # or search by name. Drive API uses IDs mostly.

    async def connect(self) -> bool:
        try:
            logger.info("[GoogleDriveConnector] Connecting to Google Drive...")
            
            if not self.credentials_path:
                raise ValueError("Service account credentials path (access_key) not provided.")

            def _connect():
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path, 
                    scopes=['https://www.googleapis.com/auth/drive']
                )
                service = build('drive', 'v3', credentials=credentials)
                
                # Test connection
                service.about().get(fields="user").execute()
                return service

            self.service = await asyncio.to_thread(_connect)
            logger.info("[GoogleDriveConnector] Connection successful.")
            return True
        except HttpError as e:
            logger.error(f"[GoogleDriveConnector] Connection Failed (HttpError): {e}")
            raise
        except Exception as e:
            logger.error(f"[GoogleDriveConnector] Connection Failed: {e}")
            raise

    async def disconnect(self) -> bool:
        try:
            logger.info("[GoogleDriveConnector] Disconnecting...")
            if self.service:
                # googleapiclient discovery resources don't require an explicit close, 
                # but we'll clear the reference
                self.service = None
            logger.info("[GoogleDriveConnector] Disconnected.")
            return True
        except Exception as e:
            logger.error(f"[GoogleDriveConnector] Disconnect Error: {e}")
            raise

    def _resolve_folder_id(self, path: str) -> str:
        # Drive API uses 'root' for root directory
        return path if path else 'root'

    async def list_folders(self, path: str = "") -> List[str]:
        try:
            logger.info(f"[GoogleDriveConnector] Listing folders in path: '{path}'")
            if not self.service:
                await self.connect()

            folder_id = self._resolve_folder_id(path)

            def _list_folders():
                query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                results = self.service.files().list(
                    q=query, spaces='drive', fields='files(id, name)'
                ).execute()
                
                folders = []
                for item in results.get('files', []):
                    folders.append(item.get('name'))
                return folders

            return await asyncio.to_thread(_list_folders)
        except HttpError as e:
            if e.resp.status == 404:
                logger.error(f"[GoogleDriveConnector] Folder not found: {path}")
                raise FileNotFoundError(f"Folder not found: {path}")
            logger.error(f"[GoogleDriveConnector] Error listing folders: {e}")
            raise
        except Exception as e:
            logger.error(f"[GoogleDriveConnector] Error listing folders: {e}")
            raise

    async def list_files(self, path: str = "") -> List[Dict[str, Any]]:
        try:
            logger.info(f"[GoogleDriveConnector] Listing files in path: '{path}'")
            if not self.service:
                await self.connect()

            folder_id = self._resolve_folder_id(path)

            def _list_files():
                query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
                results = self.service.files().list(
                    q=query, spaces='drive', fields='files(id, name, size, modifiedTime)'
                ).execute()
                
                files = []
                for item in results.get('files', []):
                    file_name = item.get('name')
                    extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""
                    files.append({
                        "name": file_name,
                        "path": item.get('id'), # Using ID as path for subsequent operations
                        "size": int(item.get('size', 0)),
                        "type": extension,
                        "modified": item.get('modifiedTime')
                    })
                return files

            return await asyncio.to_thread(_list_files)
        except HttpError as e:
            if e.resp.status == 404:
                logger.error(f"[GoogleDriveConnector] Folder not found: {path}")
                raise FileNotFoundError(f"Folder not found: {path}")
            logger.error(f"[GoogleDriveConnector] Error listing files: {e}")
            raise
        except Exception as e:
            logger.error(f"[GoogleDriveConnector] Error listing files: {e}")
            raise

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        try:
            logger.info(f"[GoogleDriveConnector] Getting metadata for path (file ID): '{path}'")
            if not self.service:
                await self.connect()

            def _get_metadata():
                file = self.service.files().get(
                    fileId=path, 
                    fields="id, name, size, createdTime, modifiedTime"
                ).execute()
                
                file_name = file.get('name')
                extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""

                return {
                    "name": file_name,
                    "extension": extension,
                    "size": int(file.get('size', 0)),
                    "created": file.get('createdTime'),
                    "modified": file.get('modifiedTime'),
                    "storage": "Google Drive"
                }

            return await asyncio.to_thread(_get_metadata)
        except HttpError as e:
            if e.resp.status == 404:
                logger.error(f"[GoogleDriveConnector] File Missing: {path}")
                raise FileNotFoundError(f"File not found: {path}")
            logger.error(f"[GoogleDriveConnector] SDK Error: {e}")
            raise
        except Exception as e:
            logger.error(f"[GoogleDriveConnector] SDK Error: {e}")
            raise

    async def read_file(self, path: str) -> str:
        try:
            logger.info(f"[GoogleDriveConnector] Reading File (file ID): '{path}'")
            if not self.service:
                await self.connect()

            def _read_file():
                request = self.service.files().get_media(fileId=path)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                return fh.getvalue().decode('utf-8')

            return await asyncio.to_thread(_read_file)
        except HttpError as e:
            if e.resp.status == 404:
                logger.error(f"[GoogleDriveConnector] File Missing: {path}")
                raise FileNotFoundError(f"File not found: {path}")
            logger.error(f"[GoogleDriveConnector] SDK Error: {e}")
            raise
        except Exception as e:
            logger.error(f"[GoogleDriveConnector] SDK Error: {e}")
            raise

    async def download_file(self, path: str, destination: str) -> bool:
        try:
            logger.info(f"[GoogleDriveConnector] Downloading file '{path}' to '{destination}'")
            if not self.service:
                await self.connect()

            def _download_file():
                request = self.service.files().get_media(fileId=path)
                with open(destination, 'wb') as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while done is False:
                        status, done = downloader.next_chunk()

            await asyncio.to_thread(_download_file)
            return True
        except HttpError as e:
            if e.resp.status == 404:
                logger.error(f"[GoogleDriveConnector] File Missing: {path}")
                raise FileNotFoundError(f"File not found: {path}")
            logger.error(f"[GoogleDriveConnector] SDK Error: {e}")
            raise
        except Exception as e:
            logger.error(f"[GoogleDriveConnector] SDK Error: {e}")
            raise
