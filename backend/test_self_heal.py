import requests

url = 'https://api-rankroute.vocoweb.in/api/v1/chat'
headers = {
    'Content-Type': 'application/json'
}
data = {
    'session_id': 'test-self-healing-001',
    'message': 'Who is the principal of Dibrugarh University Institute of Engineering and Technology (DUIET)?',
    'history': []
}

print('Sending request to production API...')
try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print(f'Status: {response.status_code}')
    # It streams, so just print the first few chunks
    for chunk in response.iter_content(chunk_size=1024):
        if chunk:
            print(chunk.decode('utf-8'))
except Exception as e:
    print(f'Error: {e}')
