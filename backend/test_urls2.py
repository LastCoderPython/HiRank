import sys
import os
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.domain_registry import COLLEGE_DOMAINS

urls = []
for domains in COLLEGE_DOMAINS.values():
    for d in domains:
        urls.append(f"https://{d}/")

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("--- COLLEGE_DOMAINS DIAGNOSTIC REPORT ---")
for url in urls:
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        print(f"[{response.status_code}] {url}")
    except Exception as e:
        print(f"[ERROR] {url} -> {type(e).__name__}")
print("-----------------------------------------")
