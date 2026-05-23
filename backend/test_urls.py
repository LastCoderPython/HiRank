import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

urls = [
    'https://www.aec.ac.in/',
    'https://www.jecassam.ac.in/',
    'https://www.nits.ac.in/',
    'https://www.tezu.ernet.in/',
    'https://jist.ac.in/',
    'https://www.bbec.ac.in/',
    'https://www.bvec.ac.in/',
    'https://www.dec.ac.in/',
    'https://www.gecassam.ac.in/',
    'https://www.astu.ac.in/',
    'https://dte.assam.gov.in/',
    'https://josaa.nic.in/',
    'https://www.dibru.ac.in/duiet',
    'https://gauhati.ac.in/academic/institutes/gauhati-university-institute-of-science-and-technology'
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("--- URL DIAGNOSTIC REPORT ---")
for url in urls:
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        print(f"[{response.status_code}] {url}")
    except Exception as e:
        print(f"[ERROR] {url} -> {type(e).__name__}")
print("-----------------------------")
