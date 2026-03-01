#!/usr/bin/env python3
"""Debug normalize-and-extract endpoint"""

import requests
import json

BASE_URL = "http://localhost:5000"

# Test the normalize-and-extract endpoint
print("=" * 60)
print("TEST: Normalize and Extract")
print("=" * 60)

test_text = """DD FORM 1289
I HEV 71
000 PRESCRIPTION
FOR PA name attens, $ phone - 0 under 12, - -
John & 853. USN
V.5.5 Never/orgetten (00/78)
MEDICAL FACILITY
U.S.S Neverforgetten (00 178)
23 July
Amoxicillin 500mg
Metformin 1000mg daily
Allergies: Penicillin"""

payload = {
    "reviewed_text": test_text,
    "patient_verified": True,
    "ocr_confidence": 56.16
}

try:
    print(f"Sending request...")
    response = requests.post(
        f"{BASE_URL}/ai/normalize-and-extract",
        json=payload,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {response.headers}")
    print(f"Response Text: {response.text[:500]}")
    
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
