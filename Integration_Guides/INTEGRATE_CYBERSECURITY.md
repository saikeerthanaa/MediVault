# Cybersecurity Integration Guide — MediVault AI Pipeline

## Overview

The AI pipeline exposes REST endpoints that return **consistent JSON**. This guide provides the exact JSON keys, data types, and structure for every endpoint so you can implement deterministic hashing, authentication, and encryption.

---

## Step 1: Understand the API Surface

The AI pipeline has **10 endpoints**. All return JSON with `"ok": true/false` as the first field.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/ai/process-document` | OCR — extract text from prescription image |
| POST | `/ai/normalize-and-extract` | NLP — normalize text + extract medical entities |
| POST | `/ai/check-interaction` | RAG — check drug interactions |
| POST | `/ai/tts` | TTS — generate audio summary |
| POST | `/ai/emergency-summary` | Generate emergency medical summary |
| POST | `/ai/to-fhir` | Convert entities to FHIR 4.0 bundle |
| POST | `/ai/save-prescription` | Save prescription to MySQL |
| POST | `/ai/save-lab-report` | Upload lab report to S3 + MySQL |
| GET | `/ai/test-bedrock` | Health check — AI service status |
| GET | `/ai/check-database` | Health check — database status |

---

## Step 2: JSON Output Structure (For Deterministic Hashing)

### Endpoint: POST /ai/process-document

```json
{
  "ok": true,
  "raw_text": "string",
  "confidence": 85.5,
  "requires_review": false,
  "blocks": [
    {
      "type": "string",
      "text": "string",
      "confidence": 98.5,
      "geometry": {
        "bounding_box": { "left": 0.1, "top": 0.2, "width": 0.3, "height": 0.05 },
        "page": 1
      }
    }
  ]
}
```

**Keys:** `ok`, `raw_text`, `confidence`, `requires_review`, `blocks`

---

### Endpoint: POST /ai/normalize-and-extract

```json
{
  "ok": true,
  "normalized": {
    "cleaned_text": "string",
    "confidence": 0.92,
    "flags": ["string"],
    "corrections": [
      {
        "original": "string",
        "corrected": "string",
        "type": "string",
        "confidence": 0.99,
        "source": "string"
      }
    ],
    "needs_term_review": false
  },
  "entities": {
    "medications": [
      {
        "name": "string",
        "dosage": "string",
        "frequency": "string",
        "duration": "string",
        "schedule": {
          "frequency": "string",
          "timing": ["string"],
          "duration": "string",
          "route": "string",
          "uncertainty": false,
          "normalized_display": "string"
        }
      }
    ],
    "conditions": ["string"],
    "allergies": ["string"],
    "instructions": ["string"]
  }
}
```

**Keys:** `ok`, `normalized`, `entities`

---

### Endpoint: POST /ai/check-interaction

```json
{
  "ok": true,
  "interactions": [
    {
      "medication": "string",
      "severity": "high|medium|low|unknown",
      "summary": "string",
      "description": "string",
      "mechanism": "string",
      "action": "string",
      "citations": [
        {
          "title": "string",
          "snippet": "string",
          "source_uri": "string",
          "relevance_score": 0.98
        }
      ]
    }
  ]
}
```

**Keys:** `ok`, `interactions`
**Severity values (always lowercase):** `"high"`, `"medium"`, `"low"`, `"unknown"`

---

### Endpoint: POST /ai/tts

```json
{
  "ok": true,
  "audio_url": "data:audio/mpeg;base64,<base64string>",
  "voice_id": "string"
}
```

**Keys:** `ok`, `audio_url`, `voice_id`
**Note:** `audio_url` changes per call — exclude from hash.

---

### Endpoint: POST /ai/save-prescription

```json
{
  "ok": true,
  "prescription_id": 42,
  "medicines_saved": 2,
  "interactions": [
    {
      "pair": ["string", "string"],
      "severity": "high|medium",
      "summary": "string",
      "description": "string",
      "action": "string"
    }
  ],
  "fhir_bundle_saved": true,
  "warnings": ["string"]
}
```

**Keys:** `ok`, `prescription_id`, `medicines_saved`, `interactions`, `fhir_bundle_saved`, `warnings`

---

### Endpoint: POST /ai/save-lab-report

```json
{
  "ok": true,
  "lab_report_id": 15,
  "s3_url": "string",
  "message": "Lab report saved successfully"
}
```

**Keys:** `ok`, `lab_report_id`, `s3_url`, `message`
**Note:** `s3_url` is unique per upload — exclude from hash if needed.

---

### Endpoint: POST /ai/emergency-summary

```json
{
  "ok": true,
  "emergency_bundle": {
    "allergies": [
      { "allergen": "string", "severity": "string", "reaction": "string" }
    ],
    "current_meds": [
      { "name": "string", "dosage": "string", "frequency": "string", "is_critical": false }
    ],
    "chronic_conditions": ["string"],
    "key_risks": ["string"]
  },
  "short_text": "string"
}
```

**Keys:** `ok`, `emergency_bundle`, `short_text`

---

### Error Response (All Endpoints)

```json
{
  "ok": false,
  "error": "string"
}
```

**HTTP codes:** 400 (bad input), 404 (not found), 500 (server error)

---

## Step 3: Hashing Guidelines

### Which Fields to Hash

| Field | Type | Hashable | Why |
|-------|------|----------|-----|
| `ok` | boolean | Yes | Always present, deterministic |
| `prescription_id` | integer | Yes | Unique, stable |
| `medicines_saved` | integer | Yes | Deterministic count |
| `fhir_bundle_saved` | boolean | Yes | Always true/false |
| `interactions` | array | Yes | Same input = same output |
| `warnings` | array | Yes | Deterministic |
| `error` | string | Yes | Stable error messages |
| `audio_url` | string | **No** | Changes per synthesis call |
| `s3_url` | string | **No** | Unique per upload (has timestamp) |
| `created_at` | string | **No** | Timestamp, always different |

### How to Create a Deterministic Hash

```python
import json
import hashlib

def hash_response(response_dict, exclude_keys=None):
    """Create SHA-256 hash of API response for integrity verification."""
    exclude = exclude_keys or {'audio_url', 's3_url', 'created_at', 'updated_at'}
    
    # Remove non-deterministic fields
    clean = {k: v for k, v in response_dict.items() if k not in exclude}
    
    # Sort keys for deterministic ordering
    canonical = json.dumps(clean, sort_keys=True, separators=(',', ':'))
    
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# Example usage:
response = {
    "ok": True,
    "prescription_id": 42,
    "medicines_saved": 2,
    "fhir_bundle_saved": True,
    "interactions": [],
    "warnings": []
}

hash_value = hash_response(response)
# Always produces the same hash for the same data
```

---

## Step 4: Adding Authentication

### Option A: Add a before_request hook to app.py

Add this to `backend/app.py` inside the `create_app()` function, after the CORS setup:

```python
    @app.before_request
    def check_auth():
        # Skip auth for static files and health checks
        if request.path == '/' or request.path.startswith('/static'):
            return None
        
        # Skip auth for health check endpoints (optional)
        if request.path in ['/ai/test-bedrock']:
            return None
        
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({"ok": False, "error": "Authorization token required"}), 401
        
        # Validate token (Cognito, JWT, or your auth system)
        user = validate_token(token)
        if not user:
            return jsonify({"ok": False, "error": "Invalid or expired token"}), 403
        
        # Attach user info to request context
        request.user = user
```

**What this does:** Every `/ai/*` request must include `Authorization: Bearer <token>` header. Without it, the request is rejected before reaching any endpoint. The existing endpoint code stays untouched.

### Option B: Use AWS API Gateway (No Code Changes)

Put API Gateway in front of the Flask server. API Gateway handles auth before requests reach Flask:

```
User Request → API Gateway (validates token) → Flask App (processes request)
                     ↓ No valid token
                  ❌ 401 Unauthorized
```

The AI pipeline code changes: **zero**.

---

## Step 5: Where to Add Encryption

### Data at Rest
- **MySQL:** Enable RDS encryption (AES-256) when creating the RDS instance
- **S3:** Enable SSE-S3 or SSE-KMS on the `medivault-lab-reports` bucket:
  ```bash
  aws s3api put-bucket-encryption \
    --bucket medivault-lab-reports \
    --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms"}}]}'
  ```

### Data in Transit
- **HTTPS:** Configure SSL certificate on the Flask server or use AWS ALB with SSL termination
- **Database connection:** Enable SSL in MySQL connection by adding to `config.py`:
  ```python
  MYSQL_SSL = {"ca": "/path/to/rds-ca-cert.pem"}
  ```

### Sensitive Fields in JSON
Fields containing personal health information (PHI):

| Field | Endpoint | Classification |
|-------|----------|---------------|
| `raw_text` | process-document | PHI — contains prescription text |
| `cleaned_text` | normalize-and-extract | PHI — normalized prescription |
| `medications[].name` | normalize-and-extract | PHI — medication names |
| `conditions[]` | normalize-and-extract | PHI — medical conditions |
| `allergies[]` | normalize-and-extract | PHI — patient allergies |
| `fhir_bundle` | save-prescription | PHI — complete medical record |
| `audio_url` | tts | PHI — audio of prescription summary |
| `emergency_bundle` | emergency-summary | PHI — critical medical info |

---

## Step 6: Rate Limiting

Currently there is no rate limiting. Add this using Flask-Limiter:

```python
# Add to backend/requirements.txt:
flask-limiter==3.5.0

# Add to backend/app.py:
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour", "10 per minute"]
)

# Apply to specific endpoints:
@app.post("/ai/process-document")
@limiter.limit("5 per minute")  # OCR is expensive
def process_document():
    ...

@app.post("/ai/tts")
@limiter.limit("10 per minute")  # TTS is moderate cost
def tts():
    ...
```

---

## Step 7: Audit Logging

All database writes go through `backend/services/db_service.py`. Add audit logging there:

```python
# Suggested: log every database write
import logging

audit_logger = logging.getLogger('medivault.audit')
audit_logger.setLevel(logging.INFO)

# Log format: timestamp | user | action | table | record_id
# Example: 2026-03-01 14:23:45 | patient_123 | INSERT | prescriptions | 42
```

### Endpoints That Write to Database

| Endpoint | Tables Modified | Action |
|----------|----------------|--------|
| `POST /ai/save-prescription` | prescriptions, medicines, prescription_medicines | INSERT |
| `POST /ai/save-lab-report` | lab_reports | INSERT |

All other endpoints are read-only (no database writes).

---

## Step 8: Current Security Status

| Security Measure | Status | Notes |
|-----------------|--------|-------|
| CORS | ✅ Configured | Allows `*` in dev, restrict in production |
| SQL Injection | ✅ Protected | All queries use parameterized statements |
| XSS | ⚠️ Partial | JSON-only API, no HTML rendering |
| Authentication | ❌ Not implemented | Needs Cognito/JWT integration |
| Rate Limiting | ❌ Not implemented | Needs Flask-Limiter |
| HTTPS | ❌ Not implemented | Needs SSL cert or ALB |
| Encryption at Rest | ⚠️ Partial | S3 supports it, MySQL needs RDS encryption |
| Audit Logging | ❌ Not implemented | Needs logging middleware |
| Input Validation | ✅ Basic | File type checks, required field checks |
| Error Handling | ✅ Implemented | Returns JSON errors, never exposes stack traces to client |

---

## Data Types Reference

Every JSON response uses these types consistently:

| Type | Example | Notes |
|------|---------|-------|
| boolean | `true` / `false` | Never null |
| integer | `42` | Never negative for IDs |
| float | `85.5` | Confidence scores: 0.0–100.0 |
| string | `"Ibuprofen"` | UTF-8 encoded, never null (empty string `""` instead) |
| array | `["Fever"]` | Empty array `[]` if no items, never null |
| object | `{"name": "..."}` | Nested JSON structure |

---

## Reference Files

- `API_SCHEMA.json` — Full endpoint definitions with JSON keys and types
- `FRONTEND_DATAFLOW.json` — UI data flow and field mappings
- `DATABASE_SCHEMA.json` — Database table schemas
- `backend/app.py` — All endpoint code
- `backend/config.py` — Configuration variables
- `backend/services/db_service.py` — Database connection layer
