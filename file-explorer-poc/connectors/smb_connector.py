import logging
import asyncio
import os
from typing import List, Dict, Any
import smbclient

from .storage_connector import IStorageConnector
from config.config import StorageConfig

logger = logging.getLogger(__name__)

class SMBConnector(IStorageConnector):
    """SMB/CIFS (Windows File Server) integration."""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.server = self.config.endpoint_url
        self.share = self.config.share_name
        self.username = self.config.client_id
        self.password = self.config.client_secret
        self.is_connected = False
        
        if not self.server or not self.share:
            logger.warning("[SMBConnector] Server or share not fully configured.")

    def _get_full_path(self, path: str) -> str:
        clean_path = path.strip("\\/")
        if clean_path:
            return rf"\\{self.server}\{self.share}\{clean_path}".replace("/", "\\")
        return rf"\\{self.server}\{self.share}"

    async def connect(self) -> bool:
        try:
            logger.info("[SMBConnector] Connecting to SMB server...")
            if not self.server:
                raise ValueError("SMB server endpoint_url not provided.")
                
            def _connect():
                smbclient.register_session(
                    self.server, 
                    username=self.username, 
                    password=self.password
                )
                # Verify access to the share
                smbclient.stat(rf"\\{self.server}\{self.share}")

            await asyncio.to_thread(_connect)
            self.is_connected = True
            logger.info("[SMBConnector] Connection successful.")
            return True
        except Exception as e:
            logger.error(f"[SMBConnector] Connection Failed: {e}")
            raise

    async def disconnect(self) -> bool:
        try:
            logger.info("[SMBConnector] Disconnecting...")
            if self.is_connected:
                def _disconnect():
                    smbclient.reset_connection_cache()
                await asyncio.to_thread(_disconnect)
                self.is_connected = False
            logger.info("[SMBConnector] Disconnected.")
            return True
        except Exception as e:
            logger.error(f"[SMBConnector] Disconnect Error: {e}")
            raise

    async def list_folders(self, path: str = "") -> List[str]:
        try:
            logger.info(f"[SMBConnector] Listing folders in path: '{path}'")
            if not self.is_connected:
                await self.connect()

            full_path = self._get_full_path(path)

            def _list_folders():
                folders = []
                for entry in smbclient.scandir(full_path):
                    if entry.is_dir():
                        folders.append(entry.name)
                return folders

            return await asyncio.to_thread(_list_folders)
        except Exception as e:
            logger.error(f"[SMBConnector] Error listing folders: {e}")
            raise

    async def list_files(self, path: str = "") -> List[Dict[str, Any]]:
        try:
            logger.info(f"[SMBConnector] Listing files in path: '{path}'")
            if not self.is_connected:
                await self.connect()

            full_path = self._get_full_path(path)

            def _list_files():
                files = []
                for entry in smbclient.scandir(full_path):
                    if entry.is_file():
                        stat = entry.stat()
                        extension = f".{entry.name.split('.')[-1]}" if '.' in entry.name else ""
                        files.append({
                            "name": entry.name,
                            "path": f"{path}/{entry.name}".strip("/"),
                            "size": stat.st_size,
                            "type": extension,
                            "modified": str(stat.st_mtime)
                        })
                return files

            return await asyncio.to_thread(_list_files)
        except Exception as e:
            logger.error(f"[SMBConnector] Error listing files: {e}")
            raise

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        try:
            logger.info(f"[SMBConnector] Getting metadata for path: '{path}'")
            if not self.is_connected:
                await self.connect()

            full_path = self._get_full_path(path)

            def _get_metadata():
                stat = smbclient.stat(full_path)
                file_name = os.path.basename(clean_path := path.replace("\\", "/"))
                extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""
                
                return {
                    "name": file_name,
                    "extension": extension,
                    "size": stat.st_size,
                    "created": str(stat.st_ctime),
                    "modified": str(stat.st_mtime),
                    "storage": "SMB"
                }

            return await asyncio.to_thread(_get_metadata)
        except Exception as e:
            logger.error(f"[SMBConnector] Error getting metadata: {e}")
            raise

    async def read_file(self, path: str) -> str:
        try:
            logger.info(f"[SMBConnector] Reading File: '{path}'")
            if not self.is_connected:
                await self.connect()

            full_path = self._get_full_path(path)

            def _read_file():
                with smbclient.open_file(full_path, mode='r', encoding='utf-8') as f:
                    return f.read()

            return await asyncio.to_thread(_read_file)
        except Exception as e:
            logger.error(f"[SMBConnector] Error reading file: {e}")
            raise

    async def download_file(self, path: str, destination: str) -> bool:
        try:
            logger.info(f"[SMBConnector] Downloading file '{path}' to '{destination}'")
            if not self.is_connected:
                await self.connect()

            full_path = self._get_full_path(path)

            def _download_file():
                with smbclient.open_file(full_path, mode='rb') as f_in:
                    with open(destination, 'wb') as f_out:
                        f_out.write(f_in.read())

            await asyncio.to_thread(_download_file)
            return True
        except Exception as e:
            logger.error(f"[SMBConnector] Error downloading file: {e}")
            raise
