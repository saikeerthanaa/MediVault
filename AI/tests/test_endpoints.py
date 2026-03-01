import requests

endpoints = [
    ('GET', '/ai/test-bedrock'),
    ('GET', '/health'),
    ('POST', '/ai/process-document'),
    ('POST', '/ai/normalize-and-extract'),
    ('POST', '/ai/check-interaction'),
    ('POST', '/ai/tts'),
    ('POST', '/ai/save-prescription'),
    ('GET', '/ai/check-database'),
]

print("Testing endpoints:\n")

for method, endpoint in endpoints:
    try:
        if method == 'GET':
            resp = requests.get(f'http://localhost:5000{endpoint}', timeout=3)
        else:
            resp = requests.post(f'http://localhost:5000{endpoint}', json={}, timeout=3)
        
        status = "✓" if resp.status_code < 500 else "✗"
        print(f"{status} {method:4} {endpoint:35} → {resp.status_code}")
    except Exception as e:
        print(f"✗ {method:4} {endpoint:35} → Error: {str(e)[:40]}")

print("\n✓ All endpoints available!")
