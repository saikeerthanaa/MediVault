"""
Simple S3 upload service for MediVault
Handles uploading files to AWS S3 with optional mock mode for testing
"""

import boto3
import uuid
from datetime import datetime
from botocore.exceptions import ClientError


class S3Service:
    def __init__(self, region: str, bucket_name: str = "medivault-uploads", mock_mode: bool = False):
        """
        Initialize S3 service
        
        Args:
            region: AWS region
            bucket_name: S3 bucket name (will create if doesn't exist in config)
            mock_mode: If True, use mock S3 (for testing without AWS credentials)
        """
        self.region = region
        self.bucket_name = bucket_name
        self.mock_mode = mock_mode
        
        if not mock_mode:
            try:
                self.client = boto3.client("s3", region_name=region)
                print(f"✓ S3Service initialized for bucket '{bucket_name}' in {region}")
            except Exception as e:
                print(f"✗ Failed to initialize S3 client: {e}")
                raise
        else:
            self.client = None
            print(f"✓ S3Service initialized in MOCK mode")
    
    def upload_file(self, file_bytes: bytes, file_name: str, subfolder: str = "lab-reports") -> dict:
        """
        Upload file to S3
        
        Args:
            file_bytes: File content as bytes
            file_name: Original file name
            subfolder: Subfolder in bucket (e.g., 'lab-reports', 'prescriptions')
        
        Returns:
            dict with:
                - ok: bool
                - s3_url: str (if successful)
                - key: str (if successful)
                - error: str (if failed)
        """
        try:
            # Generate unique key to avoid collisions
            unique_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_ext = file_name.split('.')[-1] if '.' in file_name else 'pdf'
            s3_key = f"{subfolder}/{timestamp}_{unique_id}.{file_ext}"
            
            if self.mock_mode:
                # Mock mode: return fake S3 URL without uploading
                s3_url = f"s3://{self.bucket_name}/{s3_key}"
                print(f"[MOCK S3] Would upload {len(file_bytes)} bytes to {s3_url}")
                return {
                    "ok": True,
                    "s3_url": s3_url,
                    "key": s3_key,
                    "bucket": self.bucket_name,
                    "mock": True
                }
            
            # Real mode: upload to S3
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_bytes,
                ContentType=self._get_content_type(file_ext)
            )
            
            # Construct public URL (assuming public bucket)
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            return {
                "ok": True,
                "s3_url": s3_url,
                "key": s3_key,
                "bucket": self.bucket_name
            }
        
        except ClientError as e:
            return {
                "ok": False,
                "error": f"S3 upload failed: {str(e)}"
            }
        except Exception as e:
            return {
                "ok": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    @staticmethod
    def _get_content_type(file_ext: str) -> str:
        """Get MIME type for file extension"""
        types = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
        }
        return types.get(file_ext.lower(), 'application/octet-stream')
