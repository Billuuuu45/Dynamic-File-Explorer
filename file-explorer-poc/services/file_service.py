import logging
import asyncssh
import stat
from datetime import datetime
from typing import List, Dict, Any
from connectors.connector_factory import get_connector

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class FileService:
    """Service layer that acts as an intermediary between API and connector."""

    def __init__(self):
        # The service initializes the connector via the factory.
        self.connector = get_connector()
        logger.info(f"FileService initialized with connector: {self.connector.__class__.__name__}")
        
        # SSH / SFTP State
        self.ssh_conn = None
        self._sftp_client = None
        
        # Hardcoded SSH credentials
        self.ssh_host = "103.194.242.10"
        self.ssh_port = 22
        self.ssh_user = "appuser"
        self.ssh_pass = "Xyloite@123"
        self.ssh_root = "/home/appuser"

    def get_sftp(self):
        return self._sftp_client

    async def initialize(self) -> bool:
        """Initialize the underlying connection."""
        logger.info("Initializing connector connection...")
        result = await self.connector.connect()
        logger.info(f"Connector initialization result: {result}")
        
        print("\nConnecting to SSH server...")
        try:
            self.ssh_conn = await asyncssh.connect(
                self.ssh_host,
                port=self.ssh_port,
                username=self.ssh_user,
                password=self.ssh_pass,
                known_hosts=None
            )
            print("SSH Connected.")
            
            self._sftp_client = await self.ssh_conn.start_sftp_client()
            print("SFTP session started.\n")
            
            print(f"Contents of {self.ssh_root}\n")
            first_file_path = None
            
            entries = await self._sftp_client.readdir(self.ssh_root)
            for entry in entries:
                if entry.filename in ('.', '..'):
                    continue
                    
                is_dir = stat.S_ISDIR(entry.attrs.permissions)
                type_str = "DIR " if is_dir else "FILE"
                print(f"[{type_str}] {entry.filename}")
                
                if not is_dir and first_file_path is None:
                    first_file_path = f"{self.ssh_root}/{entry.filename}"
                    
            if first_file_path:
                print("\n====================================")
                print("Reading first file:")
                print(f"{first_file_path}")
                print("====================================\n")
                
                async with self._sftp_client.open(first_file_path, 'r') as f:
                    content = await f.read()
                    print(content)
                    
        except Exception as e:
            logger.error(f"SSH/SFTP Connection Failed: {e}")

        return result

    async def shutdown(self) -> bool:
        """Close the underlying connection."""
        logger.info("Shutting down connector connection...")
        result = await self.connector.disconnect()
        logger.info(f"Connector shutdown result: {result}")
        
        if self._sftp_client:
            self._sftp_client.exit()
            
        if self.ssh_conn:
            self.ssh_conn.close()
            await self.ssh_conn.wait_closed()
            
        return result

    def _get_sftp_path(self, path: str) -> str:
        clean_path = path.strip("/")
        return f"{self.ssh_root}/{clean_path}" if clean_path else self.ssh_root

    async def _recursive_search_folders(self, base_path: str, search_lower: str) -> List[str]:
        results = []
        try:
            entries = await self._sftp_client.readdir(base_path)
            for entry in entries:
                if entry.filename in ('.', '..'):
                    continue
                    
                full_path = f"{base_path}/{entry.filename}"
                if stat.S_ISDIR(entry.attrs.permissions):
                    rel_path = full_path[len(self.ssh_root)+1:]
                    if search_lower in entry.filename.lower():
                        results.append(rel_path)
                    
                    sub_results = await self._recursive_search_folders(full_path, search_lower)
                    results.extend(sub_results)
        except Exception as e:
            logger.error(f"Error recursively reading folders in {base_path}: {e}")
        return results

    async def get_folders(self, path: str = "", search: str = None) -> List[str]:
        """Get folders from the SFTP server, optionally filtered by search."""
        logger.info(f"Fetching folders for path: '{path}' with search: '{search}'")
        if not self._sftp_client:
            return []
            
        if search:
            s_lower = search.lower()
            folders = await self._recursive_search_folders(self.ssh_root, s_lower)
            folders.sort(key=lambda x: (not x.split('/')[-1].lower().startswith(s_lower), x.lower()))
            logger.info(f"Result: Found {len(folders)} folders via recursive search.")
            return folders

        target = self._get_sftp_path(path)
        try:
            entries = await self._sftp_client.readdir(target)
            folders = [
                entry.filename for entry in entries
                if stat.S_ISDIR(entry.attrs.permissions) and entry.filename not in ('.', '..')
            ]
            
            folders.sort(key=lambda x: x.lower())
                
            logger.info(f"Result: Found {len(folders)} folders.")
            return folders
        except Exception as e:
            logger.error(f"Error fetching folders: {e}")
            raise FileNotFoundError("Directory not found")

    async def _recursive_search_files(self, base_path: str, search_lower: str) -> List[Dict[str, Any]]:
        results = []
        try:
            entries = await self._sftp_client.readdir(base_path)
            for entry in entries:
                if entry.filename in ('.', '..'):
                    continue
                
                full_path = f"{base_path}/{entry.filename}"
                
                if stat.S_ISDIR(entry.attrs.permissions):
                    sub_results = await self._recursive_search_files(full_path, search_lower)
                    results.extend(sub_results)
                else:
                    if search_lower in entry.filename.lower():
                        extension = entry.filename.split('.')[-1] if '.' in entry.filename else "unknown"
                        rel_path = full_path[len(self.ssh_root)+1:]
                        results.append({
                            "name": rel_path,
                            "size": entry.attrs.size,
                            "type": extension
                        })
        except Exception as e:
            logger.error(f"Error recursively reading files in {base_path}: {e}")
        return results

    async def get_files(self, path: str = "", search: str = None) -> List[Dict[str, Any]]:
        """Get files from the SFTP server, optionally filtered by search."""
        logger.info(f"Fetching files for path: '{path}' with search: '{search}'")
        if not self._sftp_client:
            return []
            
        if search:
            s_lower = search.lower()
            files = await self._recursive_search_files(self.ssh_root, s_lower)
            files.sort(key=lambda x: (not x['name'].split('/')[-1].lower().startswith(s_lower), x['name'].lower()))
            logger.info(f"Result: Found {len(files)} files via recursive search.")
            return files

        target = self._get_sftp_path(path)
        try:
            entries = await self._sftp_client.readdir(target)
            files = []
            for entry in entries:
                if not stat.S_ISDIR(entry.attrs.permissions):
                    file_name = entry.filename
                    
                    extension = file_name.split('.')[-1] if '.' in file_name else "unknown"
                    files.append({
                        "name": file_name,
                        "size": entry.attrs.size,
                        "type": extension
                    })
            
            files.sort(key=lambda x: x['name'].lower())
                
            logger.info(f"Result: Found {len(files)} files.")
            return files
        except Exception as e:
            logger.error(f"Error fetching files: {e}")
            raise FileNotFoundError("Directory not found")

    async def get_file_metadata(self, path: str) -> Dict[str, Any]:
        """Get file metadata from the SFTP server."""
        logger.info(f"Fetching metadata for file: '{path}'")
        if not self._sftp_client:
            raise FileNotFoundError("SFTP not connected")
            
        target = self._get_sftp_path(path)
        try:
            file_stat = await self._sftp_client.stat(target)
            file_name = target.split('/')[-1]
            
            metadata = {
                "filename": file_name,
                "extension": file_name.split('.')[-1] if '.' in file_name else "unknown",
                "size": file_stat.size,
                "created_date": datetime.fromtimestamp(file_stat.atime).isoformat() if file_stat.atime else "",
                "modified_date": datetime.fromtimestamp(file_stat.mtime).isoformat() if file_stat.mtime else ""
            }
            logger.info(f"Result: Metadata retrieved successfully. Size: {metadata.get('size')} bytes.")
            return metadata
        except Exception as e:
            logger.error(f"Error fetching metadata: {e}")
            raise FileNotFoundError("File not found")

    async def read_file_content(self, path: str) -> str:
        """Read file content from the SFTP server."""
        logger.info(f"Reading content for file: '{path}'")
        if not self._sftp_client:
            raise FileNotFoundError("SFTP not connected")
            
        target = self._get_sftp_path(path)
        try:
            async with self._sftp_client.open(target, 'r') as f:
                content = await f.read()
            logger.info(f"Result: Read {len(content)} characters from file.")
            return content
        except UnicodeDecodeError:
            return f"[Unsupported File Type] This file appears to be a binary file and cannot be displayed as text."
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            raise FileNotFoundError("File not found")

    async def download_file(self, path: str, destination: str) -> bool:
        """Download file content from the SFTP server to local destination."""
        logger.info(f"Downloading file: '{path}' to '{destination}'")
        if not self._sftp_client:
            raise FileNotFoundError("SFTP not connected")
            
        target = self._get_sftp_path(path)
        try:
            import asyncssh
            await asyncssh.scp((self.ssh_conn, target), destination)
            logger.info(f"Result: Download successful.")
            return True
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return False

# Singleton instance to be used across the app
file_service = FileService()
