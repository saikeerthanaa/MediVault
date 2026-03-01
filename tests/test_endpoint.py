#!/usr/bin/env python3
"""Test the fixed /ai/normalize-and-extract endpoint."""

import json
import requests

base_url = "http://localhost:5000"

# Test 1: Simple medication extraction
print("="*70)
print("TEST 1: Simple Medication Extraction")
print("="*70)

payload = {
    "reviewed_text": "Ibuprofen 200mg BD for 7 days",
    "patient_verified": True,
    "ocr_confidence": 0.85,
    "debug": True
}

try:
    response = requests.post(
        f"{base_url}/ai/normalize-and-extract",
        json=payload,
        timeout=5
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2))
    
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: OCR with noise
print("\n" + "="*70)
print("TEST 2: OCR with Character Noise")
print("="*70)

payload = {
    "reviewed_text": "Paracetem0l 500mg BD, Ibupr0fen 200mg TDS for 7 days",
    "patient_verified": True,
    "ocr_confidence": 0.70,
    "debug": True
}

try:
    response = requests.post(
        f"{base_url}/ai/normalize-and-extract",
        json=payload,
        timeout=5
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    
    if result.get("ok"):
        print("✅ Extraction successful")
        print(f"Cleaned text: {result['normalized']['cleaned_text'][:100]}...")
        print(f"Medications found: {len(result['entities']['medications'])}")
        for med in result['entities']['medications']:
            print(f"  • {med['name']}: {med['dosage']} {med['frequency']}")
    else:
        print(f"❌ Error: {result.get('error')}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n✅ Endpoint test complete!")
