import requests
from PIL import Image
import io

# Create a simple test image
img = Image.new('RGB', (100, 100), color='red')
img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# Test 1: Upload file
print("1. Testing /ai/process-document endpoint...")
try:
    with open('/tmp/test_image.png', 'wb') as f:
        img.save(f)
    
    with open('/tmp/test_image.png', 'rb') as f:
        files = {'file': f}
        resp = requests.post('http://localhost:5000/ai/process-document', files=files, timeout=10)
    
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✓ Response OK")
        print(f"   Text extracted: {len(data.get('text', ''))} chars")
        print(f"   Confidence: {data.get('confidence', 0):.2%}")
    else:
        print(f"   Error: {resp.text[:100]}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: Normalize and extract
print("\n2. Testing /ai/normalize-and-extract endpoint...")
try:
    payload = {
        "text": "Patient: John Doe. Medications: Aspirin 500mg twice daily, Lisinopril 10mg once daily. Allergies: Penicillin."
    }
    resp = requests.post('http://localhost:5000/ai/normalize-and-extract', json=payload, timeout=10)
    
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✓ Response OK")
        print(f"   Medications: {data.get('medications', [])}")
        print(f"   Allergies: {data.get('allergies', [])}")
    else:
        print(f"   Error: {resp.text[:100]}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Check interactions
print("\n3. Testing /ai/check-interaction endpoint...")
try:
    payload = {
        "medications": ["Aspirin", "Alendronate"]
    }
    resp = requests.post('http://localhost:5000/ai/check-interaction', json=payload, timeout=10)
    
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✓ Response OK")
        print(f"   Interactions found: {len(data.get('interactions', []))}")
    else:
        print(f"   Error: {resp.text[:100]}")
except Exception as e:
    print(f"   Error: {e}")

print("\n✓ All tests completed!")
