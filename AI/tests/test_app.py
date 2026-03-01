#!/usr/bin/env python3
"""Test MediVault application endpoints"""

import requests
import json

BASE_URL = "http://localhost:5000"

# Test 1: Health check
print("=" * 60)
print("TEST 1: Health Check (GET /)")
print("=" * 60)
try:
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

# Test 2: Bedrock connection
print("\n" + "=" * 60)
print("TEST 2: Bedrock Connection (GET /ai/test-bedrock)")
print("=" * 60)
try:
    response = requests.get(f"{BASE_URL}/ai/test-bedrock")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Bedrock Status: {result.get('bedrock_status')}")
    print(f"OK: {result.get('ok')}")
    print(f"Result Summary: {result.get('result')[:150]}...")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Process document with test image
print("\n" + "=" * 60)
print("TEST 3: Process Document (POST /ai/process-document)")
print("=" * 60)
try:
    # Check if test image exists
    import os
    test_image = r"C:\Users\saik3\Downloads\prescription.png"
    if os.path.exists(test_image):
        with open(test_image, "rb") as f:
            files = {"file": f}
            response = requests.post(f"{BASE_URL}/ai/process-document", files=files)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"OK: {result.get('ok')}")
        print(f"Confidence: {result.get('confidence')}%")
        print(f"Requires Review: {result.get('requires_review')}")
        print(f"Text (first 100 chars): {result.get('raw_text', '')[:100]}...")
    else:
        print(f"Test image not found at {test_image}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("TESTING COMPLETE")
print("=" * 60)
