import json
import csv
import threading
from typing import List, Dict, Optional
from pathlib import Path


class CollegeInfoService:
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent.parent / "data" / "college_info"
        self.colleges_info = {}
        self.fee_structure = {}
        self.placement_stats = {}
        self.facilities = {}
        self.seat_matrix = {}
        self.branch_details = {}
        self.admission_processes = {}
        self._load_all_data()
    
    def _load_all_data(self):
        self._load_colleges_basic_info()
        self._load_fee_structure()
        self._load_placement_stats()
        self._load_facilities()
        self._load_seat_matrix()
        self._load_branch_details()
        self._load_admission_processes()
    
    def _load_colleges_basic_info(self):
        file_path = self.data_dir / "colleges_basic_info.csv"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get('college_code', '')
                    self.colleges_info[code] = {
                        'name': row.get('college_name', ''),
                        'short_name': row.get('short_name', ''),
                        'location': row.get('location', ''),
                        'district': row.get('district', ''),
                        'state': row.get('state', ''),
                        'established': row.get('established', ''),
                        'type': row.get('type', ''),
                        'affiliation': row.get('affiliation', ''),
                        'nirf_rank': row.get('nirf_rank', ''),
                        'website': row.get('website', ''),
                        'phone': row.get('contact_phone', ''),
                        'email': row.get('contact_email', '')
                    }
    
    def _load_fee_structure(self):
        file_path = self.data_dir / "fee_structure.csv"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get('college_code', '')
                    if code not in self.fee_structure:
                        self.fee_structure[code] = []
                    self.fee_structure[code].append({
                        'program': row.get('program', 'B.Tech'),
                        'tuition_per_sem': row.get('tuition_fee_per_sem', '0'),
                        'hostel_per_sem': row.get('hostel_fee_per_sem', '0'),
                        'total_per_sem': row.get('total_per_sem', '0'),
                        'total_first_year': row.get('total_first_year', '0'),
                        'remarks': row.get('remarks', '')
                    })
    
    def _load_placement_stats(self):
        file_path = self.data_dir / "placement_stats.csv"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get('college_code', '')
                    if code not in self.placement_stats:
                        self.placement_stats[code] = []
                    self.placement_stats[code].append({
                        'branch': row.get('branch', ''),
                        'avg_package_lpa': row.get('avg_package_lpa', '0'),
                        'highest_package_lpa': row.get('highest_package_lpa', '0'),
                        'placement_percentage': row.get('placement_percentage', '0'),
                        'top_recruiters': row.get('top_recruiters', '')
                    })
    
    def _load_facilities(self):
        file_path = self.data_dir / "facilities.csv"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get('college_code', '')
                    self.facilities[code] = {
                        'campus_area': row.get('campus_area_acres', ''),
                        'hostel_boys': row.get('hostel_boys', ''),
                        'hostel_girls': row.get('hostel_girls', ''),
                        'hostel_capacity': row.get('hostel_capacity', ''),
                        'library_books': row.get('library_books', ''),
                        'computer_labs': row.get('computer_labs', ''),
                        'sports': row.get('sports_facilities', ''),
                        'wifi': row.get('wifi_campus', ''),
                        'gym': row.get('gym', ''),
                        'medical': row.get('medical_facility', ''),
                        'bank_atm': row.get('bank_atm', ''),
                        'cafeteria': row.get('cafeteria', ''),
                        'auditorium': row.get('auditorium', ''),
                        'research_labs': row.get('research_labs', '')
                    }
    
    def _load_seat_matrix(self):
        file_path = self.data_dir / "seat_matrix.csv"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get('college_code', '')
                    if code not in self.seat_matrix:
                        self.seat_matrix[code] = {}
                    branch = row.get('branch', '')
                    self.seat_matrix[code][branch] = {
                        'total_seats': row.get('total_seats', '0'),
                        'govt_seats': row.get('govt_seats', '0')
                    }
    
    def _load_branch_details(self):
        file_path = self.data_dir / "branch_details.json"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                self.branch_details = json.load(f)
    
    def _load_admission_processes(self):
        file_path = self.data_dir / "admission_processes.json"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                self.admission_processes = json.load(f)
    
    def get_college_info(self, college_name_or_code: str) -> Optional[Dict]:
        college_name_or_code = college_name_or_code.upper().strip()
        
        if college_name_or_code in self.colleges_info:
            return self.colleges_info[college_name_or_code]
        
        for code, info in self.colleges_info.items():
            if info['name'].upper() == college_name_or_code:
                return info
            if info['short_name'] == college_name_or_code:
                return info
        
        for code, info in self.colleges_info.items():
            if college_name_or_code in info['name'].upper():
                return info
        
        return None
    
    def get_fee_structure(self, college_code: str) -> List[Dict]:
        return self.fee_structure.get(college_code.upper(), [])
    
    def get_placement_stats(self, college_code: str, branch: str = None) -> List[Dict]:
        stats = self.placement_stats.get(college_code.upper(), [])
        if branch:
            branch = branch.capitalize()
            return [s for s in stats if branch in s['branch']]
        return stats
    
    def get_facilities(self, college_code: str) -> Optional[Dict]:
        return self.facilities.get(college_code.upper())
    
    def get_seat_matrix(self, college_code: str, branch: str = None) -> Dict:
        matrix = self.seat_matrix.get(college_code.upper(), {})
        if branch and branch in matrix:
            return {branch: matrix[branch]}
        return matrix
    
    def get_branch_details(self, branch_name: str) -> Optional[Dict]:
        branches = self.branch_details.get('branches', {})
        branch_name = branch_name.title()
        
        for key, details in branches.items():
            if branch_name in key or key in branch_name:
                return details
            if details.get('full_name', '').lower() == branch_name.lower():
                return details
        
        return branches.get(branch_name)
    
    def get_admission_process(self, exam_type: str = 'cee') -> Dict:
        exam_type = exam_type.lower()
        processes = self.admission_processes.get('admission_processes', {})
        return processes.get(exam_type, {})
    
    def get_documents_required(self) -> Dict:
        return self.admission_processes.get('documents_required', {})
    
    def get_scholarships(self) -> Dict:
        return self.admission_processes.get('scholarships', {})
    
    def search_colleges(self, query: str) -> List[Dict]:
        query = query.lower()
        results = []
        
        for code, info in self.colleges_info.items():
            if (query in info['name'].lower() or 
                query in info['location'].lower() or 
                query in info['district'].lower()):
                results.append({'code': code, **info})
        
        return results
    
    def format_college_summary(self, college_name: str) -> str:
        college_code = None
        college_name_upper = college_name.upper()
        
        for code, info in self.colleges_info.items():
            if (college_name_upper == info['name'].upper() or 
                college_name_upper == info['short_name'] or
                college_name_upper == code):
                college_code = code
                break
        
        if not college_code:
            for code, info in self.colleges_info.items():
                if college_name_upper in info['name'].upper():
                    college_code = code
                    break
        
        if not college_code:
            return f"Information not found for {college_name}"
        
        info = self.colleges_info.get(college_code, {})
        facilities = self.facilities.get(college_code, {})
        fees = self.fee_structure.get(college_code, [])
        placements = self.placement_stats.get(college_code, [])
        
        summary_parts = []
        
        summary_parts.append(f"**{info.get('name', college_name)}** ({info.get('short_name', '')})")
        
        if info.get('established'):
            summary_parts.append(f"Established: {info['established']}")
        if info.get('location'):
            summary_parts.append(f"Location: {info['location']}, {info.get('district', '')}")
        if info.get('type'):
            summary_parts.append(f"Type: {info['type']} - {info.get('affiliation', '')}")
        if info.get('nirf_rank'):
            summary_parts.append(f"NIRF Rank: {info['nirf_rank']}")
        
        if facilities:
            summary_parts.append(f"\n**Campus:** {facilities.get('campus_area', 'N/A')} acres")
            summary_parts.append(f"Hostel: {facilities.get('hostel_boys', '0')} boys, {facilities.get('hostel_girls', '0')} girls")
            amenities = []
            if facilities.get('wifi') == 'Yes':
                amenities.append("Wi-Fi Campus")
            if facilities.get('gym') == 'Yes':
                amenities.append("Gym available")
            if amenities:
                summary_parts.append(", ".join(amenities))
        
        if fees:
            fee_info = fees[0]
            summary_parts.append(f"\n**Fees (First Year):** ₹{fee_info.get('total_first_year', 'N/A')}")
            if fee_info.get('remarks'):
                summary_parts.append(f"Note: {fee_info['remarks']}")
        
        if placements:
            cs_placements = [p for p in placements if 'Computer' in p.get('branch', '')]
            if cs_placements:
                cs = cs_placements[0]
                summary_parts.append(f"\n**Placements (CSE):** Avg: ₹{cs.get('avg_package_lpa', 'N/A')} LPA, Highest: ₹{cs.get('highest_package_lpa', 'N/A')} LPA")
        
        return "\n".join(summary_parts)


    def reload_all(self) -> Dict[str, int]:
        """Hot-reload all college info data from CSV/JSON files.

        Called by the admin upload endpoint after new files are written.
        Uses copy-on-write: builds new data into temporaries, then
        atomically swaps references so concurrent readers never see
        partial/empty state.
        """
        # Build new data into a temporary instance (no shared state)
        tmp = CollegeInfoService.__new__(CollegeInfoService)
        tmp.data_dir = self.data_dir
        tmp.colleges_info = {}
        tmp.fee_structure = {}
        tmp.placement_stats = {}
        tmp.facilities = {}
        tmp.seat_matrix = {}
        tmp.branch_details = {}
        tmp.admission_processes = {}
        tmp._load_all_data()

        # Atomic swap — readers will see the old OR the new, never empty
        if not hasattr(self, '_reload_lock'):
            self._reload_lock = threading.Lock()

        with self._reload_lock:
            self.colleges_info = tmp.colleges_info
            self.fee_structure = tmp.fee_structure
            self.placement_stats = tmp.placement_stats
            self.facilities = tmp.facilities
            self.seat_matrix = tmp.seat_matrix
            self.branch_details = tmp.branch_details
            self.admission_processes = tmp.admission_processes

        return {
            "colleges_info": len(self.colleges_info),
            "fee_structure": len(self.fee_structure),
            "placement_stats": len(self.placement_stats),
            "facilities": len(self.facilities),
            "seat_matrix": len(self.seat_matrix),
            "branch_details": len(self.branch_details),
            "admission_processes": len(self.admission_processes),
        }


college_info_service = CollegeInfoService()