import requests
import json

url = 'https://api-rankroute.vocoweb.in/api/v1/chat'
headers = {
    'Content-Type': 'application/json'
}
data = {
    'session_id': 'test-self-healing-003',
    'message': 'Who is the current principal of Bineswar Brahma Engineering College?',
    'history': []
}

print('Sending request to production API...')
try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print(f'Status: {response.status_code}')
    full_text = ''
    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith('data: '):
                try:
                    payload = json.loads(decoded[6:])
                    if payload.get('type') == 'token':
                        print(payload.get('data', ''), end='', flush=True)
                except json.JSONDecodeError:
                    pass
    
    print('\n\nResponse received!')
except Exception as e:
    print(f'Error: {e}')
