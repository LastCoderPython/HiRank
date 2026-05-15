from typing import List, Dict, Any
from app.models.requests import ParsedQuery
from app.services.college_info_service import college_info_service


class ContextBuilder:
    def __init__(self):
        self.college_info = college_info_service
    
    def build(
        self,
        parsed_query: ParsedQuery,
        retrieved_docs: List[Dict[str, Any]]
    ) -> str:
        if not retrieved_docs:
            return self._build_no_results_context(parsed_query)
        
        sections = []
        
        sections.append(self._build_header(parsed_query))
        sections.append(self._build_query_summary(parsed_query))
        sections.append(self._build_college_list(retrieved_docs))
        sections.append(self._build_college_details(retrieved_docs))
        sections.append(self._build_analysis(parsed_query, retrieved_docs))
        sections.append(self._build_admission_info(parsed_query))
        sections.append(self._build_disclaimer())
        
        return "\n\n".join(sections)
    
    def _build_header(self, parsed_query: ParsedQuery) -> str:
        return f"""=== CEE/JEE ADMISSION DATA ===
Retrieved {parsed_query.exam or "CEE"} cutoff data for analysis.
Query Intent: {parsed_query.intent.upper()}"""
    
    def _build_query_summary(self, parsed_query: ParsedQuery) -> str:
        lines = ["=== USER QUERY PARAMETERS ==="]
        lines.append(f"Rank: {parsed_query.rank or 'Not specified'}")
        lines.append(f"Category: {parsed_query.category}")
        lines.append(f"Exam: {parsed_query.exam or 'CEE'}")
        if parsed_query.branch:
            lines.append(f"Branch Preference: {parsed_query.branch}")
        lines.append(f"Original Question: '{parsed_query.raw_query}'")
        return "\n".join(lines)
    
    def _build_college_list(self, docs: List[Dict[str, Any]]) -> str:
        lines = ["=== ELIGIBLE COLLEGES (ONLY MENTION THESE COLLEGES) ==="]
        lines.append("IMPORTANT: Only discuss colleges listed below. Do NOT mention any other colleges.")
        lines.append("")
        
        college_names = set()
        user_category_results = []
        other_category_results = []
        
        for i, doc in enumerate(docs, 1):
            metadata = doc["metadata"]
            match = doc["match_percentage"]
            college_name = metadata.get('college_name', 'Unknown')
            category = metadata.get('category', 'General')
            college_names.add(college_name)
            
            if i <= 20:
                lines.append(f"{i}. {college_name} - {metadata.get('branch', 'N/A')}")
                lines.append(f"   Category: {category} | Closing Rank: {metadata.get('closing_rank', 'N/A')} | Match: {match:.1f}%")
                lines.append("")
        
        lines.append(f"\nAVAILABLE COLLEGES IN THIS RESULT: {', '.join(sorted(college_names))}")
        lines.append("")
        lines.append("=== CATEGORY NOTE ===")
        lines.append("Results include your selected category + other categories that may be relevant.")
        lines.append("Only mention colleges that are listed above.")
        
        return "\n".join(lines)
    
    def _build_college_details(self, docs: List[Dict[str, Any]]) -> str:
        lines = ["=== COLLEGE DETAILS ==="]
        seen_colleges = set()
        
        for doc in docs[:10]:
            metadata = doc.get("metadata", {})
            college_name = metadata.get("college_name", "")
            college_code = metadata.get("college_code", "")
            
            if college_name and college_name not in seen_colleges:
                seen_colleges.add(college_name)
                college_info = self.college_info.get_college_info(college_name)
                
                if college_info:
                    code = college_name.split('(')[-1].replace(')', '').strip() if '(' in college_name else college_code
                    for c in [college_code, code]:
                        if c:
                            college_code = c
                            break
                    
                    lines.append(f"\n**{college_name}**")
                    if college_info.get('location'):
                        lines.append(f"Location: {college_info['location']}, {college_info.get('district', '')}")
                    if college_info.get('established'):
                        lines.append(f"Established: {college_info['established']}")
                    if college_info.get('type'):
                        lines.append(f"Type: {college_info['type']}")
                    if college_info.get('nirf_rank'):
                        lines.append(f"NIRF Rank: {college_info['nirf_rank']}")
                
                code = metadata.get("college_code", "")
                fees = self.college_info.get_fee_structure(code)
                if fees:
                    fee_data = fees[0]
                    lines.append(f"Approximate First Year Fee: ₹{fee_data.get('total_first_year', 'Contact college')}")
                    if fee_data.get('remarks'):
                        lines.append(f"Note: {fee_data['remarks']}")
                
                placements = self.college_info.get_placement_stats(code, metadata.get("branch", ""))
                if placements:
                    p = placements[0]
                    lines.append(f"Average Package: ₹{p.get('avg_package_lpa', 'N/A')} LPA")
                    lines.append(f"Top Recruiters: {p.get('top_recruiters', 'Various')}")
        
        return "\n".join(lines)
    
    def _build_admission_info(self, parsed_query: ParsedQuery) -> str:
        lines = ["=== ADMISSION PROCESS INFO ==="]
        
        exam_type = (parsed_query.exam or "CEE").lower()
        admission_info = self.college_info.get_admission_process(exam_type)
        
        if admission_info:
            lines.append(f"\n**{admission_info.get('full_name', exam_type.upper())} Counseling Steps:**")
            counseling_steps = admission_info.get("counseling_process", []) or admission_info.get("counseling_process_joasaa", [])
            
            for step in counseling_steps[:5]:
                lines.append(f"Step {step.get('step', '?')}: {step.get('title', '')}")
                lines.append(f"  {step.get('description', '')}")
        
        lines.append("\n**Required Documents:**")
        docs_required = self.college_info.get_documents_required()
        general_docs = docs_required.get("general", [])
        if general_docs:
            lines.append("General: " + ", ".join(general_docs[:5]))
        
        return "\n".join(lines)
    
    def _build_analysis(
        self,
        parsed_query: ParsedQuery,
        docs: List[Dict[str, Any]]
    ) -> str:
        lines = ["=== ANALYSIS GUIDELINES ==="]
        
        if parsed_query.rank:
            user_rank = parsed_query.rank
            
            safe_options = [d for d in docs if d["match_percentage"] >= 90]
            moderate_options = [d for d in docs if 70 <= d["match_percentage"] < 90]
            risky_options = [d for d in docs if d["match_percentage"] < 70]
            
            lines.append(f"User Rank: {user_rank}")
            lines.append(f"Safe Options (Match >= 90%): {len(safe_options)}")
            lines.append(f"Moderate Options (Match 70-90%): {len(moderate_options)}")
            lines.append(f"Risky Options (Match < 70%): {len(risky_options)}")
            lines.append("")
            lines.append("RECOMMENDATION PRIORITY:")
            lines.append("1. List safe colleges first (high confidence)")
            lines.append("2. Then moderate probability colleges")
            lines.append("3. Finally mention risky/borderline options")
            lines.append("4. Suggest backup options from higher closing ranks")
        
        return "\n".join(lines)
    
    def _build_disclaimer(self) -> str:
        return """=== IMPORTANT DISCLAIMERS ===
1. Data is from previous year cutoffs and may vary this year
2. Actual cutoffs depend on number of applicants, seat matrix, etc.
3. This is a prediction tool, actual results may differ
4. Always verify with official DTE/JOSAA notifications
5. Consider 5-10% buffer on closing ranks for safety"""
    
    def _build_no_results_context(self, parsed_query: ParsedQuery) -> str:
        query = parsed_query.raw_query.lower()
        lines = ["=== GENERAL QUERY INFO ==="]
        
        college_keywords = {
            'aec': 'AEC',
            'assam engineering college': 'AEC',
            'jec': 'JEC',
            'jorhat engineering college': 'JEC',
            'jist': 'JIST',
            'jorhat institute': 'JIST',
            'bbec': 'BBEC',
            'bineswar brahma': 'BBEC',
            'bvec': 'BVEC',
            'barak valley': 'BVEC',
            'dec': 'DEC',
            'dhemaji': 'DEC',
            'gec': 'GEC',
            'golaghat': 'GEC',
            'nits': 'NITS',
            'nit silchar': 'NITS',
            'tezu': 'TU',
            'tezpur university': 'TU',
            'duiet': 'DUIET',
            'dibrugarh': 'DUIET'
        }
        
        detected_college = None
        for keyword, code in college_keywords.items():
            if keyword in query:
                detected_college = code
                break
        
        if detected_college:
            college_info = self.college_info.get_college_info(detected_college)
            if college_info:
                lines.append(f"\n**{college_info.get('name', detected_college)}**")
                lines.append(f"Location: {college_info.get('location', 'N/A')}, {college_info.get('district', '')}")
                lines.append(f"Established: {college_info.get('established', 'N/A')}")
                lines.append(f"Type: {college_info.get('type', 'Government')}")
                if college_info.get('nirf_rank'):
                    lines.append(f"NIRF Rank: {college_info.get('nirf_rank')}")
            
            fees = self.college_info.get_fee_structure(detected_college)
            if fees:
                fee_data = fees[0]
                lines.append(f"\n**Fee Structure:**")
                lines.append(f"Tuition per semester: ₹{fee_data.get('tuition_per_sem', 'N/A')}")
                lines.append(f"Hostel per semester: ₹{fee_data.get('hostel_per_sem', 'N/A')}")
                lines.append(f"Total first year: ₹{fee_data.get('total_first_year', 'N/A')}")
                if fee_data.get('remarks'):
                    lines.append(f"Note: {fee_data['remarks']}")
            
            placements = self.college_info.get_placement_stats(detected_college)
            if placements:
                lines.append(f"\n**Placements (Branch-wise):**")
                for p in placements[:3]:
                    lines.append(f"  {p.get('branch', 'N/A')}: Avg ₹{p.get('avg_package_lpa', 'N/A')} LPA, Top: ₹{p.get('highest_package_lpa', 'N/A')} LPA")
                    lines.append(f"    Recruiters: {p.get('top_recruiters', 'Various')[:50]}...")
            
            facilities = self.college_info.get_facilities(detected_college)
            if facilities:
                lines.append(f"\n**Facilities:**")
                lines.append(f"Campus: {facilities.get('campus_area', 'N/A')} acres")
                lines.append(f"Hostel: Boys-{facilities.get('hostel_boys', '0')}, Girls-{facilities.get('hostel_girls', '0')}")
                if facilities.get('wifi') == 'Yes':
                    lines.append("Wi-Fi enabled campus")
        else:
            lines.append("No specific college detected in query.")
        
        if 'fee' in query or 'fees' in query:
            if not detected_college:
                lines.append("\n**Fee Information:**")
                lines.append("NIT Silchar: ₹2,41,000/year (first year)")
                lines.append("Tezpur University: ₹1,52,000/year (first year)")
                lines.append("AEC/JEC: ₹99,000/year (first year)")
                lines.append("State colleges (BBEC/BVEC/DEC/GEC): ₹94,000/year (first year)")
        
        if 'placement' in query or 'package' in query or 'salary' in query:
            lines.append("\n**Placement Highlights:**")
            lines.append("NIT Silchar (CSE): Avg ₹14.5 LPA, Highest ₹45 LPA")
            lines.append("Tezpur University (CSE): Avg ₹8.5 LPA, Highest ₹28 LPA")
            lines.append("AEC (CSE): Avg ₹6 LPA, Highest ₹18 LPA")
            lines.append("State colleges (CSE): Avg ₹3-4 LPA")
        
        lines.append("\n=== INSTRUCTIONS ===")
        lines.append("Use the above data to answer the user's question.")
        lines.append("Be specific and helpful. Reference actual figures from the data.")
        
        return "\n".join(lines)
    
    def format_for_display(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for doc in docs:
            metadata = doc.get("metadata", {})
            formatted.append({
                "college_name": metadata.get("college_name", ""),
                "college_code": metadata.get("college_code", ""),
                "branch": metadata.get("branch", ""),
                "category": metadata.get("category", "General"),
                "opening_rank": metadata.get("opening_rank", 0),
                "closing_rank": metadata.get("closing_rank", 0),
                "year": metadata.get("year", 2023),
                "match_percentage": doc.get("match_percentage", 0),
                "seat_type": metadata.get("seat_type", "Government")
            })
        return formatted


context_builder = ContextBuilder()
