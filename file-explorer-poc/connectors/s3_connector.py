import logging
import datetime
import asyncio
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from .storage_connector import IStorageConnector
from config.config import StorageConfig

logger = logging.getLogger(__name__)

class S3Connector(IStorageConnector):
    """Amazon S3 integration."""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.s3_client = None
        self.bucket_name = self.config.bucket_name

    async def connect(self) -> bool:
        try:
            logger.info("[S3Connector] Connecting to S3...")
            
            if not self.bucket_name:
                raise ValueError("Bucket name is not configured for S3.")

            def _connect():
                client = boto3.client(
                    's3',
                    aws_access_key_id=self.config.access_key,
                    aws_secret_access_key=self.config.secret_key,
                    region_name=self.config.region,
                    endpoint_url=self.config.endpoint_url
                )
                # Test the connection by getting bucket location or head bucket
                client.head_bucket(Bucket=self.bucket_name)
                return client

            self.s3_client = await asyncio.to_thread(_connect)
            logger.info("[S3Connector] Connection successful.")
            return True
        except ClientError as e:
            logger.error(f"[S3Connector] Connection Failed (ClientError): {e}")
            raise
        except BotoCoreError as e:
            logger.error(f"[S3Connector] Connection Failed (BotoCoreError): {e}")
            raise
        except Exception as e:
            logger.error(f"[S3Connector] Unexpected Connection Error: {e}")
            raise

    async def disconnect(self) -> bool:
        try:
            logger.info("[S3Connector] Disconnecting from S3...")
            if self.s3_client:
                def _disconnect():
                    self.s3_client.close()
                await asyncio.to_thread(_disconnect)
                self.s3_client = None
            logger.info("[S3Connector] Disconnected.")
            return True
        except Exception as e:
            logger.error(f"[S3Connector] Disconnect Error: {e}")
            raise

    async def list_folders(self, path: str = "") -> List[str]:
        try:
            logger.info(f"[S3Connector] Listing folders in path: '{path}'")
            if not self.s3_client:
                await self.connect()

            prefix = path if not path or path.endswith('/') else f"{path}/"
            if prefix == "/":
                prefix = ""

            def _list_folders():
                paginator = self.s3_client.get_paginator('list_objects_v2')
                folders = []
                
                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix, Delimiter='/'):
                    for common_prefix in page.get('CommonPrefixes', []):
                        folder_path = common_prefix.get('Prefix')
                        if folder_path:
                            folder_name = folder_path[len(prefix):].strip('/')
                            if folder_name:
                                folders.append(folder_name)
                return folders

            return await asyncio.to_thread(_list_folders)
        except ClientError as e:
            logger.error(f"[S3Connector] ClientError listing folders: {e}")
            raise
        except Exception as e:
            logger.error(f"[S3Connector] Error listing folders: {e}")
            raise

    async def list_files(self, path: str = "") -> List[Dict[str, Any]]:
        try:
            logger.info(f"[S3Connector] Listing files in path: '{path}'")
            if not self.s3_client:
                await self.connect()

            prefix = path if not path or path.endswith('/') else f"{path}/"
            if prefix == "/":
                prefix = ""

            def _list_files():
                paginator = self.s3_client.get_paginator('list_objects_v2')
                files = []
                
                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix, Delimiter='/'):
                    for obj in page.get('Contents', []):
                        obj_key = obj.get('Key')
                        if obj_key == prefix:
                            continue # Skip the directory object itself

                        file_name = obj_key[len(prefix):]
                        extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""
                        
                        modified = obj.get('LastModified')
                        if isinstance(modified, datetime.datetime):
                            modified = modified.isoformat()

                        files.append({
                            "name": file_name,
                            "path": obj_key,
                            "size": obj.get('Size', 0),
                            "type": extension,
                            "modified": modified
                        })
                return files

            return await asyncio.to_thread(_list_files)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucket':
                logger.error(f"[S3Connector] Bucket not found: {self.bucket_name}")
                raise FileNotFoundError(f"Bucket not found: {self.bucket_name}")
            logger.error(f"[S3Connector] ClientError listing files: {e}")
            raise
        except Exception as e:
            logger.error(f"[S3Connector] Error listing files: {e}")
            raise

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        try:
            logger.info(f"[S3Connector] Getting metadata for path: '{path}'")
            if not self.s3_client:
                await self.connect()

            def _get_metadata():
                response = self.s3_client.head_object(Bucket=self.bucket_name, Key=path)
                
                file_name = path.split('/')[-1]
                extension = f".{file_name.split('.')[-1]}" if '.' in file_name else ""

                modified = response.get('LastModified')
                if isinstance(modified, datetime.datetime):
                    modified = modified.isoformat()

                return {
                    "name": file_name,
                    "extension": extension,
                    "size": response.get('ContentLength', 0),
                    "created": modified,  # S3 doesn't typically provide creation time natively via head
                    "modified": modified,
                    "storage": "Amazon S3"
                }

            return await asyncio.to_thread(_get_metadata)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"[S3Connector] File Missing: {path}")
                raise FileNotFoundError(f"File not found: {path}")
            logger.error(f"[S3Connector] SDK Error getting metadata: {e}")
            raise
        except Exception as e:
            logger.error(f"[S3Connector] SDK Error: {e}")
            raise

    async def read_file(self, path: str) -> str:
        try:
            logger.info(f"[S3Connector] Reading File: '{path}'")
            if not self.s3_client:
                await self.connect()

            def _read_file():
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=path)
                return response['Body'].read().decode('utf-8')

            return await asyncio.to_thread(_read_file)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.error(f"[S3Connector] File Missing: {path}")
                raise FileNotFoundError(f"File not found: {path}")
            logger.error(f"[S3Connector] ClientError reading file: {e}")
            raise
        except Exception as e:
            logger.error(f"[S3Connector] SDK Error: {e}")
            raise

    async def download_file(self, path: str, destination: str) -> bool:
        try:
            logger.info(f"[S3Connector] Downloading file '{path}' to '{destination}'")
            if not self.s3_client:
                await self.connect()

            def _download_file():
                self.s3_client.download_file(self.bucket_name, path, destination)

            await asyncio.to_thread(_download_file)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"[S3Connector] File Missing: {path}")
                raise FileNotFoundError(f"File not found: {path}")
            logger.error(f"[S3Connector] ClientError downloading file: {e}")
            raise
        except Exception as e:
            logger.error(f"[S3Connector] SDK Error: {e}")
            raise
