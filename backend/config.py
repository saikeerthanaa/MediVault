import os

class Config:
    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

    # Bedrock - Amazon Nova Micro (Converse API)
    BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")

    # Knowledge Base (optional for MVP)
    BEDROCK_KB_ID = os.getenv("BEDROCK_KB_ID", "")   # empty => return "unknown risk"

    # Polly
    POLLY_VOICE_ID = os.getenv("POLLY_VOICE_ID", "Aditi")  # pick per language later

    # Simple thresholds from your requirements
    TEXTRACT_CONFIDENCE_REVIEW_THRESHOLD = float(os.getenv("TEXTRACT_CONFIDENCE_REVIEW_THRESHOLD", "60"))
    NORMALIZATION_CONFIDENCE_FLAG_THRESHOLD = float(os.getenv("NORMALIZATION_CONFIDENCE_FLAG_THRESHOLD", "70"))

    # Optional AI features (design.md)
    ENABLE_COMPREHEND_MEDICAL = os.getenv("ENABLE_COMPREHEND_MEDICAL", "false").lower() == "true"
    DEBUG_AI = os.getenv("DEBUG_AI", "false").lower() == "true"
    
    # Block-level OCR (for HITL highlighting)
    TEXTRACT_RETURN_BLOCKS = True  # Always return blocks for frontend rendering
