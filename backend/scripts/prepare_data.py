"""
Data preparation script for RankRoute RAG pipeline.
Consolidates all CSV files from frontend/src/lib into unified format for ChromaDB.
"""
import csv
import os
from pathlib import Path

BASE_DIR = Path(r"E:\RankRoute\frontend\src\lib")
OUTPUT_DIR = Path(r"E:\RankRoute\backend\data")

COLLEGE_CODES = {
    "Assam Engineering College": "AEC",
    "Jorhat Engineering College": "JEC",
    "Jorhat Institute Of Science & Technology": "JIST",
    "Barak Valley Engineering College": "BVEC",
    "Bineswar Brahma Engineering College": "BBEC",
    "Dhemaji Engineering College": "DEC",
    "Golaghat Engineering College": "GEC",
    "Gauhati University Institute of Science and Technology": "GUIST",
    "Gauhati University": "GU",
    "Tezpur University": "TU",
    "Dibrugarh University Institute of Engineering and Technology": "DUIET",
    "Dibrugarh University": "DU",
    "Assam University Silchar": "AUS",
    "Assam University": "AUS",
    "NIT Silchar": "NITS",
    "IIIT Guwahati": "IIITG",
}

BRANCH_MAPPING = {
    "Computer Science Engineering": "Computer Science",
    "Computer Science Engineering (CSE)": "Computer Science",
    "CSE": "Computer Science",
    "Electronics & Telecommunication Engineering": "Electronics",
    "Electronics and Communication Engineering": "Electronics",
    "Electronics & Communication (ECE)": "Electronics",
    "Electronics & Communication Engineering": "Electronics",
    "ECE": "Electronics",
    "Electrical Engineering": "Electrical",
    "Electrical Engineering (EE)": "Electrical",
    "EE": "Electrical",
    "Mechanical Engineering": "Mechanical",
    "Mechanical Engineering (ME)": "Mechanical",
    "Civil Engineering": "Civil",
    "Civil Engineering (CE)": "Civil",
    "Chemical Engineering": "Chemical",
    "Instrumentation Engineering": "Instrumentation",
    "Industrial & Production Engineering": "Industrial & Production",
    "Information Technology": "Information Technology",
    "Information Technology (IT)": "Information Technology",
    "IT": "Information Technology",
    "Power Electronics & Instrumentation Engineering": "Power Electronics",
    "Biotechnology": "Biotechnology",
    "Food Engineering & Technology": "Food Engineering",
    "Petroleum Engineering": "Petroleum",
}

CATEGORY_MAPPING = {
    "General": "General",
    "GENERAL": "General",
    "UR": "General",
    "OBC": "OBC",
    "OBC-NCL": "OBC",
    "MOBC": "OBC",
    "obc": "OBC",
    "SC": "SC",
    "sc": "SC",
    "ST": "ST",
    "ST(P)": "STP",
    "ST(H)": "STH",
    "STP": "STP",
    "STH": "STH",
    "EWS": "EWS",
    "ews": "EWS",
}

def normalize_branch(branch: str) -> str:
    branch_clean = branch.strip()
    return BRANCH_MAPPING.get(branch_clean, branch_clean)

def normalize_category(category: str) -> str:
    cat_clean = category.strip()
    return CATEGORY_MAPPING.get(cat_clean, cat_clean)

def get_college_code(college_name: str) -> str:
    college_clean = college_name.strip()
    return COLLEGE_CODES.get(college_clean, college_clean[:3].upper())

def update_college_code(college_name: str) -> str:
    college_clean = college_name.strip()
    for name, code in COLLEGE_CODES.items():
        if name.lower() in college_clean.lower():
            return code
    return college_clean[:3].upper()

def process_cutf(collection: list) -> dict:
    result = []
    for row in collection:
        result.append(row)
    return result

def parse_cEE_2023_file(filepath: Path, category: str) -> list:
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                college_name = row.get('institute_name', '').strip().strip('"')
                college_code = update_college_code(college_name)
                branch = normalize_branch(row.get('branch_name', '').strip().strip('"'))
                cut_off_rank = row.get('cut_off_rank', '0').strip().strip('"')
                year = row.get('year', '2023').strip().strip('"')
                round_no = row.get('round_no', '1').strip().strip('"')
                
                try:
                    rank = int(cut_off_rank)
                    year_int = int(year)
                except:
                    continue
                
                records.append({
                    "college_name": college_name,
                    "college_code": college_code,
                    "branch": branch,
                    "category": category,
                    "opening_rank": rank,
                    "closing_rank": rank,
                    "year": year_int,
                    "seat_type": "Government",
                    "exam": "CEE",
                    "round": round_no
                })
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
    return records

def parse_CEE_2024_file(filepath: Path) -> list:
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                college_name = row.get('institute_name', '').strip().strip('"')
                if not college_name:
                    continue
                college_code = update_college_code(college_name)
                branch = normalize_branch(row.get('branch_name', '').strip().strip('"'))
                category = normalize_category(row.get('category', 'General').strip().strip('"'))
                cut_off_rank = row.get('cut_off_rank', '0').strip().strip('"')
                year = row.get('year', '2024').strip().strip('"')
                round_no = row.get('round_no', '1').strip().strip('"')
                
                try:
                    rank = int(cut_off_rank)
                    year_int = int(year)
                except:
                    continue
                
                records.append({
                    "college_name": college_name,
                    "college_code": college_code,
                    "branch": branch,
                    "category": category,
                    "opening_rank": rank,
                    "closing_rank": rank,
                    "year": year_int,
                    "seat_type": "Government",
                    "exam": "CEE",
                    "round": round_no
                })
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
    return records

def parse_JEE_nit_file(filepath: Path, year: int) -> list:
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) < 2:
            return records
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            parts = [p.strip().strip('"') for p in line.split(',')]
            
            if len(parts) < 5:
                continue
            
            try:
                branch_raw = parts[0]
                category = parts[1]
                quota = parts[2]
                opening_rank = parts[3]
                closing_rank = parts[4]
                
                branch = normalize_branch(branch_raw)
                category = normalize_category(category)
                
                opening = int(opening_rank.replace(',', ''))
                closing = int(closing_rank.replace(',', ''))
                
                records.append({
                    "college_name": "NIT Silchar",
                    "college_code": "NITS",
                    "branch": branch,
                    "category": category,
                    "opening_rank": opening,
                    "closing_rank": closing,
                    "year": year,
                    "seat_type": "Government",
                    "exam": "JEE",
                    "quota": quota,
                    "round": "Last"
                })
            except (ValueError, IndexError) as e:
                continue
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
    return records

def parse_JEE_other_file(filepath: Path, college_name: str, college_code: str, year: int) -> list:
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) < 2:
            return records
        
        header_line = lines[0].strip()
        expected_fields = ['Branch', 'Category', f'{year} Round 1 Closing Rank (JEE Main)', f'{year} Last Round Closing Rank (JEE Main)']
        field_indices = {}
        
        if 'Branch,Category' in header_line:
            if 'Actual Cutoff Marks' in header_line:
                field_indices = {'branch': 0, 'category': 1, 'opening': 3, 'closing': 4}
            else:
                field_indices = {'branch': 0, 'category': 1, 'opening': 2, 'closing': 3}
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            parts = [p.strip().strip('"') for p in line.split(',')]
            
            if len(parts) < 4:
                continue
            
            try:
                branch_idx = field_indices.get('branch', 0)
                category_idx = field_indices.get('category', 1)
                opening_idx = field_indices.get('opening', 2)
                closing_idx = field_indices.get('closing', 3)
                
                branch_raw = parts[branch_idx] if branch_idx < len(parts) else ''
                category_raw = parts[category_idx] if category_idx < len(parts) else 'General'
                opening_raw = parts[opening_idx] if opening_idx < len(parts) else '0'
                closing_raw = parts[closing_idx] if closing_idx < len(parts) else '0'
                
                branch = normalize_branch(branch_raw)
                category = normalize_category(category_raw)
                
                opening = int(opening_raw.replace(',', ''))
                closing = int(closing_raw.replace(',', ''))
                
                records.append({
                    "college_name": college_name,
                    "college_code": college_code,
                    "branch": branch,
                    "category": category,
                    "opening_rank": opening,
                    "closing_rank": closing,
                    "year": year,
                    "seat_type": "Government",
                    "exam": "JEE",
                    "quota": "HS",
                    "round": "Last"
                })
            except (ValueError, IndexError) as e:
                continue
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
    return records

def main():
    cee_records = []
    jee_records = []
    
    print("=" * 60)
    print("PROCESSING CEE 2023 DATA")
    print("=" * 60)
    
    cee_2023_files = {
        "cutoff_2023_general.csv": "General",
        "cutoff_2023_obc.csv": "OBC",
        "cutoff_2023_sc.csv": "SC",
        "cutoff_2023_ews.csv": "EWS",
        "cutoff_2023_mobc.csv": "OBC",
        "cutoff_2023_st.csv": "ST",
    }
    
    for filename, category in cee_2023_files.items():
        filepath = BASE_DIR / filename
        if filepath.exists() and filepath.stat().st_size > 0:
            records = parse_cEE_2023_file(filepath, category)
            cee_records.extend(records)
            print(f"  {filename}: {len(records)} records")
        else:
            print(f"  {filename}: SKIPPED (empty or missing)")
    
    print("\n" + "=" * 60)
    print("PROCESSING CEE 2024 DATA")
    print("=" * 60)
    
    cee_2024_files = [
        "cutoffs_2024_GENERAL.csv",
        "cutoffs_2024_OBC.csv",
        "cutoffs_2024_SC.csv",
        "cutoffs_2024_EWS.csv",
        "cutoffs_2024_STH.csv",
        "cutoffs_2024_STP.csv",
    ]
    
    for filename in cee_2024_files:
        filepath = BASE_DIR / filename
        if filepath.exists() and filepath.stat().st_size > 0:
            records = parse_CEE_2024_file(filepath)
            cee_records.extend(records)
            print(f"  {filename}: {len(records)} records")
        else:
            print(f"  {filename}: SKIPPED (empty or missing)")
    
    print("\n" + "=" * 60)
    print("PROCESSING JEE DATA (NIT Silchar)")
    print("=" * 60)
    
    nit_files = {
        "nitsilchar_2023_cutoffs - Sheet1.csv": 2023,
        "nitsilchar_2024_cutoffs - Sheet1.csv": 2024,
        "nit_silchar_2025 - Sheet1.csv": 2025,
    }
    
    for filename, year in nit_files.items():
        filepath = BASE_DIR / filename
        if filepath.exists():
            records = parse_JEE_nit_file(filepath, year)
            jee_records.extend(records)
            print(f"  {filename}: {len(records)} records")
    
    print("\n" + "=" * 60)
    print("PROCESSING JEE DATA (Other Institutes)")
    print("=" * 60)
    
    other_jee_files = [
        ("tu_2023_cutoffs - Sheet1.csv", "Tezpur University", "TU", 2023),
        ("tu_2024_cutoffs - Sheet1.csv", "Tezpur University", "TU", 2024),
        ("tu_2025_cutoffs - Sheet1.csv", "Tezpur University", "TU", 2025),
        ("gu_2023_cutoffs - Sheet1.csv", "Gauhati University", "GU", 2023),
        ("gu_2024_cutoffs - Sheet1.csv", "Gauhati University", "GU", 2024),
        ("gu_2025_cutoffs - Sheet1.csv", "Gauhati University", "GU", 2025),
        ("du_2023_cutoffs - Sheet1.csv", "Dibrugarh University", "DU", 2023),
        ("du_2024_cutoffs - Sheet1.csv", "Dibrugarh University", "DU", 2024),
        ("du_2025_cutoffs - Sheet1.csv", "Dibrugarh University", "DU", 2025),
    ]
    
    for filename, college_name, college_code, year in other_jee_files:
        filepath = BASE_DIR / filename
        if filepath.exists():
            records = parse_JEE_other_file(filepath, college_name, college_code, year)
            jee_records.extend(records)
            print(f"  {filename}: {len(records)} records")
    
    cee_records = [r for i, r in enumerate(cee_records) 
                   if r not in cee_records[:i]]
    
    jee_records = [r for i, r in enumerate(jee_records) 
                   if r not in jee_records[:i]]
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total CEE records: {len(cee_records)}")
    print(f"Total JEE records: {len(jee_records)}")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    cee_output = OUTPUT_DIR / "cee_cutoffs_unified.csv"
    if cee_records:
        with open(cee_output, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ["college_name", "college_code", "branch", "category", 
                        "opening_rank", "closing_rank", "year", "seat_type", "exam", "round"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in cee_records:
                writer.writerow({k: record.get(k, '') for k in fieldnames})
        print(f"\nCEE data written to: {cee_output}")
    
    jee_output = OUTPUT_DIR / "jee_cutoffs_unified.csv"
    if jee_records:
        with open(jee_output, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ["college_name", "college_code", "branch", "category", 
                        "opening_rank", "closing_rank", "year", "seat_type", "exam", "quota", "round"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in jee_records:
                writer.writerow({k: record.get(k, '') for k in fieldnames})
        print(f"JEE data written to: {jee_output}")
    
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    
    if cee_records:
        colleges = set(r['college_name'] for r in cee_records)
        branches = set(r['branch'] for r in cee_records)
        categories = set(r['category'] for r in cee_records)
        years = set(r['year'] for r in cee_records)
        print(f"\nCEE Colleges ({len(colleges)}): {sorted(colleges)}")
        print(f"CEE Branches ({len(branches)}): {sorted(branches)}")
        print(f"CEE Categories ({len(categories)}): {sorted(categories)}")
        print(f"CEE Years: {sorted(years)}")
    
    if jee_records:
        colleges = set(r['college_name'] for r in jee_records)
        branches = set(r['branch'] for r in jee_records)
        categories = set(r['category'] for r in jee_records)
        years = set(r['year'] for r in jee_records)
        print(f"\nJEE Colleges ({len(colleges)}): {sorted(colleges)}")
        print(f"JEE Branches ({len(branches)}): {sorted(branches)}")
        print(f"JEE Categories ({len(categories)}): {sorted(categories)}")
        print(f"JEE Years: {sorted(years)}")

if __name__ == "__main__":
    main()
