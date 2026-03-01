#!/usr/bin/env python3
"""
Simple test script for POST /ai/save-prescription endpoint
Run this after starting the Flask server: python backend/app.py
"""

import requests
import json

BASE_URL = "http://localhost:5000"

print("\n" + "="*70)
print("🏥 MediVault Save-Prescription Endpoint - Manual Test")
print("="*70)

# Test 1: Basic prescription
print("\n[TEST 1] Basic Prescription")
print("-"*70)

payload = {
    "patient_id": 1,
    "doctor_id": 2,
    "s3_image_url": "https://bucket.s3.amazonaws.com/test.jpg",
    "entities": {
        "medications": [
            {
                "name": "Aspirin",
                "dosage": "100 mg",
                "frequency": "Once daily",
                "duration": "7 days"
            }
        ],
        "conditions": ["Fever"],
        "allergies": ["Penicillin"]
    }
}

print("Sending request...")
print(json.dumps(payload, indent=2))

try:
    response = requests.post(f"{BASE_URL}/ai/save-prescription", json=payload, timeout=10)
    print(f"\nStatus: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print("Make sure Flask server is running: python backend/app.py")

# Test 2: High-risk prescription
print("\n" + "="*70)
print("[TEST 2] High-Risk Prescription (Warfarin + NSAIDs)")
print("-"*70)

payload2 = {
    "patient_id": 2,
    "doctor_id": 1,
    "s3_image_url": "https://bucket.s3.amazonaws.com/high-risk.jpg",
    "entities": {
        "medications": [
            {
                "name": "Warfarin",
                "dosage": "5 mg",
                "frequency": "Once daily",
                "duration": ""
            },
            {
                "name": "Ibuprofen",
                "dosage": "400 mg",
                "frequency": "Twice daily",
                "duration": "7 days"
            },
            {
                "name": "Aspirin",
                "dosage": "81 mg",
                "frequency": "Once daily",
                "duration": ""
            }
        ],
        "conditions": ["Atrial fibrillation"],
        "allergies": []
    }
}

print("Sending request with high interaction risk...")
print(json.dumps(payload2, indent=2))

try:
    response = requests.post(f"{BASE_URL}/ai/save-prescription", json=payload2, timeout=10)
    print(f"\nStatus: {response.status_code}")
    print("Response:")
    resp_data = response.json()
    print(json.dumps(resp_data, indent=2))
    
    if resp_data.get("ok"):
        interactions = resp_data.get("interactions", [])
        if interactions:
            print("\n🚨 HIGH RISK DETECTED:")
            for i in interactions:
                print(f"  • {i['pair'][0]} + {i['pair'][1]}: {i['severity'].upper()}")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print("Make sure Flask server is running: python backend/app.py")

print("\n" + "="*70)
print("✅ Tests complete!")
print("="*70)
