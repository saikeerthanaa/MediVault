#!/usr/bin/env python3
"""Test the POST /ai/save-lab-report endpoint"""

import requests
import io
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000"

print("\n" + "="*70)
print("TEST: Lab Reports API Endpoint")
print("="*70)

# Test 1: Verify endpoint exists
print("\n[TEST 1] Check endpoint availability")
print("-" * 70)
try:
    response = requests.post(
        f"{BASE_URL}/ai/save-lab-report",
        timeout=5
    )
    print(f"✓ Endpoint is accessible (status: {response.status_code})")
except Exception as e:
    print(f"✗ Endpoint error: {e}")
    exit(1)

# Test 2: Missing file error
print("\n[TEST 2] Missing file - should return error")
print("-" * 70)
response = requests.post(
    f"{BASE_URL}/ai/save-lab-report",
    data={
        "patient_id": 1,
        "test_date": "2026-03-01",
        "report_type": "Blood"
    }
)
result = response.json()
print(f"Status: {response.status_code}")
print(f"Response: {result}")
if not result.get("ok") and "file" in result.get("error", "").lower():
    print("✓ Correctly returned error for missing file")
else:
    print("✗ Did not return expected error")

# Test 3: Missing test_date error
print("\n[TEST 3] Missing test_date - should return error")
print("-" * 70)
# Create a dummy file
dummy_file = io.BytesIO(b"dummy pdf content")
response = requests.post(
    f"{BASE_URL}/ai/save-lab-report",
    data={
        "patient_id": 1,
        "report_type": "Blood"
    },
    files={"file": ("test.pdf", dummy_file, "application/pdf")}
)
result = response.json()
print(f"Status: {response.status_code}")
print(f"Response: {result}")
if not result.get("ok") and "test_date" in result.get("error", "").lower():
    print("✓ Correctly returned error for missing test_date")
else:
    print("✗ Did not return expected error")

# Test 4: Missing report_type error
print("\n[TEST 4] Missing report_type - should return error")
print("-" * 70)
dummy_file = io.BytesIO(b"dummy pdf content")
response = requests.post(
    f"{BASE_URL}/ai/save-lab-report",
    data={
        "patient_id": 1,
        "test_date": "2026-03-01"
    },
    files={"file": ("test.pdf", dummy_file, "application/pdf")}
)
result = response.json()
print(f"Status: {response.status_code}")
if not result.get("ok") and "report_type" in result.get("error", "").lower():
    print("✓ Correctly returned error for missing report_type")
else:
    print("✗ Did not return expected error")

# Test 5: Invalid report_type error
print("\n[TEST 5] Invalid report_type - should return error")
print("-" * 70)
dummy_file = io.BytesIO(b"dummy pdf content")
response = requests.post(
    f"{BASE_URL}/ai/save-lab-report",
    data={
        "patient_id": 1,
        "test_date": "2026-03-01",
        "report_type": "InvalidType"
    },
    files={"file": ("test.pdf", dummy_file, "application/pdf")}
)
result = response.json()
print(f"Status: {response.status_code}")
if not result.get("ok") and "Invalid report_type" in result.get("error", ""):
    print("✓ Correctly rejected invalid report_type")
else:
    print("✗ Did not reject invalid report_type")

# Test 6: All required fields present - will fail on S3 but we can check structure
print("\n[TEST 6] All required fields - expect S3 error (no AWS config)")
print("-" * 70)
dummy_file = io.BytesIO(b"dummy pdf content")
response = requests.post(
    f"{BASE_URL}/ai/save-lab-report",
    data={
        "patient_id": 1,
        "test_date": "2026-03-01",
        "report_type": "Blood",
        "lab_name": "Test Lab"
    },
    files={"file": ("test.pdf", dummy_file, "application/pdf")}
)
result = response.json()
print(f"Status: {response.status_code}")
print(f"Response: {result}")
if not result.get("ok"):
    error_msg = result.get("error", "")
    if "S3" in error_msg or "endpoint" in error_msg.lower():
        print("✓ Failed on S3 upload (expected without AWS credentials)")
    else:
        print(f"Note: Got error: {error_msg}")
else:
    print("✓ Surprisingly succeeded (AWS may be configured)")
    if "lab_report_id" in result:
        print(f"  Lab Report ID: {result['lab_report_id']}")

print("\n" + "="*70)
print("✓ API endpoint tests completed")
print("="*70 + "\n")
