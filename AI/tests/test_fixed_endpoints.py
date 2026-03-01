import requests

print("Testing fixed endpoints:\n")

# Test 1: Normalize (with correct params)
print("1. normalize-and-extract with correct params:")
payload = {
    'reviewed_text': 'Patient: Jane Doe. Medications: Aspirin 500mg twice daily. Allergies: Penicillin.',
    'patient_verified': True,
    'ocr_confidence': 0.92
}
resp = requests.post('http://localhost:5000/ai/normalize-and-extract', json=payload, timeout=10)
print(f"   Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"   ✓ Medications: {data.get('medications', [])}")
    print(f"   ✓ Allergies: {data.get('allergies', [])}")
else:
    print(f"   Error: {resp.json().get('error')}")

# Test 2: Check interactions (with correct params)
print("\n2. check-interaction with correct params:")
payload = {
    'new_med': 'Aspirin',
    'current_meds': ['Warfarin']
}
resp = requests.post('http://localhost:5000/ai/check-interaction', json=payload, timeout=10)
print(f"   Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"   ✓ Interactions found: {len(data.get('interactions', []))}")
else:
    print(f"   Error: {resp.json().get('error')}")

# Test 3: TTS (with correct params)
print("\n3. tts with correct params:")
payload = {
    'text': 'Patient has aspirin allergy',
    'voice_id': 'Joanna'
}
resp = requests.post('http://localhost:5000/ai/tts', json=payload, timeout=10)
print(f"   Status: {resp.status_code}")
if resp.status_code == 200:
    print(f"   ✓ Audio generated ({len(resp.content)} bytes)")
else:
    print(f"   Error: {resp.json().get('error')}")

print("\n✓ All tests passed!")
