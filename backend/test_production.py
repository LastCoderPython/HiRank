import requests

url = 'https://api-rankroute.vocoweb.in/api/v1/chat'
headers = {
    'Content-Type': 'application/json'
}
data = {
    'session_id': 'test-self-healing-002',
    'message': 'Who is the current principal of Jorhat Engineering College?',
    'history': []
}

print('Sending request to production API...')
try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print(f'Status: {response.status_code}')
    full_text = ''
    for chunk in response.iter_content(chunk_size=1024):
        if chunk:
            decoded = chunk.decode('utf-8')
            full_text += decoded
    
    print('Response received!')
except Exception as e:
    print(f'Error: {e}')
