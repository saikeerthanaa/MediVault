import json

ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "medications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dosage": {"type": "string"},
                    "frequency": {"type": "string"},
                    "duration": {"type": "string"},
                    "route": {"type": "string"},
                    "notes": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "conditions": {"type": "array", "items": {"type": "string"}},
        "allergies": {"type": "array", "items": {"type": "string"}},
        "lab_values": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "test": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "reference_range": {"type": "string"}
                },
                "required": ["test", "value"]
            }
        }
    },
    "required": ["medications", "conditions", "allergies", "lab_values"]
}

def safe_json_loads(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None