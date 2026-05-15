import requests
import json
import time
import csv
import os

BASE_URL = "https://cee-college-predictor-backend.hf.space/api/v1/cutoffs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36",
    "Origin": "https://cee-assam-college-predictor.vercel.app",
    "Referer": "https://cee-assam-college-predictor.vercel.app/",
    "Content-Type": "application/json"
}

COLLEGES = [
    "Assam Engineering College",
    "Barak Valley Engineering College", 
    "Bineswar Brahma Engineering College",
    "Dhemaji Engineering College",
    "Golaghat Engineering College",
    "Jorhat Engineering College",
    "Jorhat Institute Of Science & Technology"
]

BRANCHES = [
    "Civil Engineering",
    "Mechanical Engineering",
    "Computer Science Engineering",
    "Industrial & Production Engineering",
    "Instrumentation Engineering",
    "Electrical Engineering",
    "Chemical Engineering",
    "Electronics & Telecommunication Engineering",
    "Power Electronics & Instrumentation Engineering"
]

CATEGORIES = [
    "GENERAL", "FF", "RDP", "CGE", "OBC", "TGLC", "EXTGLC", "KOCH",
    "TAI AHOM", "CHUTIYA", "MORAN", "MATAK", "SC", "STP", "STH", "PH", "EWS"
]

OUTPUT_DIR = r"E:\RankRoute\frontend\src\lib"

def fetch_cutoffs(college, branch, category, delay=3):
    payload = {
        "year": "2024",
        "college": college,
        "branch": branch,
        "category": category,
        "round": None,
        "govt_reservation": 0
    }
    
    time.sleep(delay)
    
    try:
        response = requests.post(BASE_URL, headers=HEADERS, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        elif response.status_code == 429:
            print(f"Rate limited, waiting 60s...")
            time.sleep(60)
            return fetch_cutoffs(college, branch, category, delay=10)
        else:
            print(f"Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"Exception: {e}")
        return []

def save_to_csv(data, category):
    if not data:
        return
    
    filepath = os.path.join(OUTPUT_DIR, f"cutoffs_2024_{category}.csv")
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['institute_name', 'branch_name', 'round_no', 'year', 'cut_off_rank', 'cut_off_marks', 'category'])
        for item in data:
            writer.writerow([
                item.get('institute_name', ''),
                item.get('branch_name', ''),
                item.get('round_no', ''),
                item.get('year', ''),
                item.get('cut_off_rank', ''),
                item.get('cut_off_marks', ''),
                category
            ])
    print(f"Saved {category}: {len(data)} records")

def main():
    all_data = {cat: [] for cat in CATEGORIES}
    
    for category in CATEGORIES:
        print(f"\nFetching {category}...")
        for college in COLLEGES:
            for branch in BRANCHES:
                data = fetch_cutoffs(college, branch, category)
                if data:
                    all_data[category].extend(data)
                    print(f"  {college} - {branch}: {len(data)} records")
        
        save_to_csv(all_data[category], category)
    
    # Save combined data
    combined = []
    for cat, data in all_data.items():
        combined.extend(data)
    
    combined_file = os.path.join(OUTPUT_DIR, "cutoffs_2024_all.json")
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump({"data": combined}, f, indent=2)
    
    print(f"\nTotal records: {len(combined)}")
    print("Done!")

if __name__ == "__main__":
    main()
