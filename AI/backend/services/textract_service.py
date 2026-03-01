import boto3
from botocore.exceptions import ClientError
from typing import Dict, List, Any, Optional

class TextractService:
    def __init__(self, region: str):
        self.client = boto3.client("textract", region_name=region)

    def detect_text_from_image_bytes(self, image_bytes: bytes) -> dict:
        """
        For hackathon MVP: supports JPEG/PNG image bytes using DetectDocumentText.
        Returns both raw_text and block-level information for HITL highlighting.
        (PDF requires async + S3; keep it out for now.)
        """
        try:
            resp = self.client.detect_document_text(
                Document={"Bytes": image_bytes}
            )
        except ClientError as e:
            return {
                "ok": False,
                "error": str(e),
                "raw_text": "",
                "confidence": 0.0,
                "blocks": []
            }

        lines = []
        confs = []
        blocks = []
        
        # Extract text and build block info
        for block in resp.get("Blocks", []):
            block_type = block.get("BlockType", "")
            
            if block_type == "LINE":
                txt = block.get("Text", "").strip()
                if txt:
                    lines.append(txt)
                    c = block.get("Confidence")
                    if c is not None:
                        confs.append(float(c))
                    
                    # Extract geometry for HITL highlighting
                    geometry = block.get("Geometry", {})
                    bounding_box = geometry.get("BoundingBox", {})
                    
                    blocks.append({
                        "type": "line",
                        "text": txt,
                        "confidence": float(c) if c is not None else 0.0,
                        "geometry": {
                            "bounding_box": {
                                "left": float(bounding_box.get("Left", 0)),
                                "top": float(bounding_box.get("Top", 0)),
                                "width": float(bounding_box.get("Width", 0)),
                                "height": float(bounding_box.get("Height", 0))
                            }
                        },
                        "page": block.get("Page", 1)
                    })
            
            elif block_type == "WORD":
                # Word-level blocks for fine-grained highlighting
                txt = block.get("Text", "").strip()
                if txt:
                    c = block.get("Confidence")
                    geometry = block.get("Geometry", {})
                    bounding_box = geometry.get("BoundingBox", {})
                    
                    blocks.append({
                        "type": "word",
                        "text": txt,
                        "confidence": float(c) if c is not None else 0.0,
                        "geometry": {
                            "bounding_box": {
                                "left": float(bounding_box.get("Left", 0)),
                                "top": float(bounding_box.get("Top", 0)),
                                "width": float(bounding_box.get("Width", 0)),
                                "height": float(bounding_box.get("Height", 0))
                            }
                        },
                        "page": block.get("Page", 1)
                    })

        raw_text = "\n".join(lines).strip()
        avg_conf = sum(confs) / len(confs) if confs else 0.0

        return {
            "ok": True,
            "raw_text": raw_text,
            "confidence": avg_conf,
            "blocks": blocks  # For HITL highlighting
        }
    
    def detect_text_from_s3(self, bucket: str, key: str) -> Dict[str, Any]:
        """
        Detect text from document stored in S3.
        Supports both images and PDFs via async processing.
        """
        try:
            # For simple case, use synchronous detection (works for <= 10 MB PDFs)
            resp = self.client.detect_document_text(
                Document={"S3Object": {"Bucket": bucket, "Name": key}}
            )
            
            lines = []
            confs = []
            blocks = []
            
            for block in resp.get("Blocks", []):
                block_type = block.get("BlockType", "")
                
                if block_type == "LINE":
                    txt = block.get("Text", "").strip()
                    if txt:
                        lines.append(txt)
                        c = block.get("Confidence")
                        if c is not None:
                            confs.append(float(c))
                        
                        geometry = block.get("Geometry", {})
                        bounding_box = geometry.get("BoundingBox", {})
                        
                        blocks.append({
                            "type": "line",
                            "text": txt,
                            "confidence": float(c) if c is not None else 0.0,
                            "geometry": {
                                "bounding_box": {
                                    "left": float(bounding_box.get("Left", 0)),
                                    "top": float(bounding_box.get("Top", 0)),
                                    "width": float(bounding_box.get("Width", 0)),
                                    "height": float(bounding_box.get("Height", 0))
                                }
                            },
                            "page": block.get("Page", 1)
                        })
            
            raw_text = "\n".join(lines).strip()
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            
            return {
                "ok": True,
                "raw_text": raw_text,
                "confidence": avg_conf,
                "blocks": blocks,
                "source": "s3"
            }
        
        except ClientError as e:
            return {
                "ok": False,
                "error": str(e),
                "raw_text": "",
                "confidence": 0.0,
                "blocks": []
            }