from typing import List, AsyncIterator, Dict, Any
from app.models.requests import ParsedQuery
from app.services.query_parser import query_parser
from app.services.retriever import retriever
from app.services.context_builder import context_builder
from app.services.college_info_service import college_info_service
from app.core.llm_client import llm_client
import re


COLLEGE_INFO_KEYWORDS = [
    'fee', 'fees', 'fee structure', 'placement', 'package', 'salary',
    'hostel', 'campus', 'facility', 'facilities', 'library', 'sports',
    'admission process', 'how to apply', 'documents', 'scholarship',
    'about', 'details', 'info', 'information'
]

COLLEGE_CODES = {
    'aec': 'AEC', 'assam engineering college': 'AEC',
    'jec': 'JEC', 'jorhat engineering college': 'JEC',
    'jist': 'JIST', 'jorhat institute': 'JIST',
    'bbec': 'BBEC', 'bineswar brahma': 'BBEC',
    'bvec': 'BVEC', 'barak valley': 'BVEC',
    'dec': 'DEC', 'dhemaji': 'DEC',
    'gec': 'GEC', 'golaghat': 'GEC',
    'nits': 'NITS', 'nit silchar': 'NITS', 'nit-silchar': 'NITS',
    'tezu': 'TU', 'tezpur university': 'TU',
    'duiet': 'DUIET', 'dibrugarh': 'DUIET',
    'gust': 'GUST', 'gauhati university': 'GUST'
}


OFF_TOPIC_PATTERNS = [
    r"\b(write|compose|create|draft|make)\s+(a|an|the)?\s*(poem|story|essay|article|song|letter|email|code|script|joke|recipe)\b",
    r"\b(translate|convert)\s+(this|the|from)\b",
    r"\b(who|what|when|where|why|how)\s+(is|are|was|were|did|does|will|would|could|should)\s+(the\s+)?(president|capital|weather|president|prime minister|president|country)\b",
    r"\b(explain|tell me about|describe)\s+(quantum|physics|chemistry|biology|history|philosophy|politics|sports|movie|music|game)\b",
    r"\b(play|sing|dance|cook)\b",
    r"\b(how\s+to|teach\s+me|learn)\s+(hack|steal|cheat|lie|attack|fight|kill|hurt)\b",
    r"\b(break|bypass|crack|hack\s+into)\s+(password|security|lock|system)\b",
    r"\b(illegal|drugs|weapons|bomb|explosive)\b",
    r"\b(i\s+love|i\s+hate|you\'re\s+stupid|you\s+suck)\b",
    r"\b(marry|date|kiss|girlfriend|boyfriend)\b",
    r"\b(what\'s\s+your\s+name|who\s+are\s+you|are\s+you\s+human|are\s+you\s+ai)\b",
    r"\b(tell\s+me\s+a\s+joke|make\s+me\s+laugh|funny)\b",
    r"\b(weather|temperature|rain|sunny)\b",
    r"\b(bitcoin|crypto|stock|share|invest|trading)\b",
    r"\b(movie|film|actor|actress|celebrity|netflix)\b",
    r"\b(football|cricket|hockey|tennis|sports|player|match)\b",
]

OFF_TOPIC_RESPONSES = [
    "I'm here to help with CEE/JEE admissions in Assam! Ask me about college predictions, cutoffs, or branch selection. 😊",
    "That's interesting, but I specialize in Assam engineering admissions. Want to know which colleges you can get based on your rank?",
    "I'm focused on helping students with CEE and JEE Mains admissions. Share your rank and I'll help you find colleges!",
    "I'd love to help, but I'm specialized for Assam CEE/JEE admissions. Tell me your rank and category for college predictions!",
    "Great question, but my expertise is in engineering admissions for Assam. Ask me about colleges, cutoffs, or branches!",
]

GREETING_RESPONSES = [
    "Hello! 👋 I'm RankRoute, your admission assistant. What's your CEE or JEE rank?",
    "Hi there! Ready to find your dream engineering college in Assam? Share your rank!",
    "Hey! I help students with CEE/JEE admissions. Tell me your rank!",
]


class RAGPipeline:
    def __init__(self):
        self.parser = query_parser
        self.retriever = retriever
        self.context_builder = context_builder
        self.llm = llm_client
    
    def _is_off_topic(self, query: str) -> bool:
        query_lower = query.lower().strip()
        
        admission_keywords = [
            'college', 'rank', 'cee', 'jee', 'admission', 'cutoff', 'branch',
            'engineering', 'aec', 'jec', 'nit', 'percentile', 'marks', 'seat',
            'counseling', 'dte', 'josaa', 'assam', 'university', 'institute',
            'computer', 'mechanical', 'civil', 'electrical', 'electronics',
            'eligib', 'predict', 'suggest', 'recommend', 'get admission', 'can i get',
            'fee', 'fees', 'placement', 'package', 'salary', 'recruit', 'company',
            'hostel', 'campus', 'facility', 'facilities', 'library', 'lab', 'sport',
            'scholarship', 'document', 'process', 'counsel', 'application', 'apply',
            'tezu', 'dibrugarh', 'jorhat', 'kokrajhar', 'silchar', 'guwahati', 'gauhati',
            'chemical', 'instrumentation', 'petroleum', 'power', 'btec', 'bbec',
            'how to apply', 'when', 'deadline', 'last date', 'important date'
        ]
        
        for keyword in admission_keywords:
            if keyword in query_lower:
                return False
        
        for pattern in OFF_TOPIC_PATTERNS:
            if re.search(pattern, query_lower):
                return True
        
        if len(query_lower.split()) < 3:
            return False
        
        return True
    
    def _is_greeting(self, query: str) -> bool:
        query_lower = query.lower().strip()
        greetings = ['hi', 'hello', 'hey', 'good morning', 'good evening', 'good afternoon', 'hola', 'howdy']
        return any(query_lower.startswith(g) for g in greetings) and len(query_lower.split()) < 5
    
    def _is_college_info_query(self, query: str) -> tuple:
        query_lower = query.lower()
        
        detected_college = None
        for keyword, code in COLLEGE_CODES.items():
            if keyword in query_lower:
                detected_college = code
                break
        
        if not detected_college:
            return None, False
        
        for keyword in COLLEGE_INFO_KEYWORDS:
            if keyword in query_lower:
                return detected_college, True
        
        return detected_college, False
    
    def _build_college_info_context(self, college_code: str, query: str) -> str:
        from app.services.college_info_service import college_info_service
        
        lines = [f"=== COLLEGE INFORMATION FOR {college_code} ==="]
        
        college_info = college_info_service.get_college_info(college_code)
        if college_info:
            lines.append(f"\n**{college_info.get('name', college_code)}**")
            lines.append(f"Location: {college_info.get('location', 'N/A')}, {college_info.get('district', '')}")
            lines.append(f"Established: {college_info.get('established', 'N/A')}")
            lines.append(f"Type: {college_info.get('type', 'Government')}")
            if college_info.get('affiliation'):
                lines.append(f"Affiliation: {college_info.get('affiliation')}")
            if college_info.get('nirf_rank'):
                lines.append(f"NIRF Rank: {college_info.get('nirf_rank')}")
            if college_info.get('website'):
                lines.append(f"Website: {college_info.get('website')}")
        
        fees = college_info_service.get_fee_structure(college_code)
        if fees:
            fee_data = fees[0]
            lines.append(f"\n**Fee Structure (B.Tech):**")
            lines.append(f"Tuition per semester: ₹{fee_data.get('tuition_per_sem', 'N/A')}")
            lines.append(f"Hostel per semester: ₹{fee_data.get('hostel_per_sem', 'N/A')}")
            lines.append(f"Other fees per semester: ₹{fee_data.get('other_fees_per_sem', 'N/A')}")
            lines.append(f"Total per semester: ₹{fee_data.get('total_per_sem', 'N/A')}")
            lines.append(f"Total first year: ₹{fee_data.get('total_first_year', 'N/A')}")
            if fee_data.get('remarks'):
                lines.append(f"Note: {fee_data['remarks']}")
        
        placements = college_info_service.get_placement_stats(college_code)
        if placements:
            lines.append(f"\n**Placement Statistics (Branch-wise):**")
            for p in placements[:5]:
                lines.append(f"  {p.get('branch', 'N/A')}:")
                lines.append(f"    Average: ₹{p.get('avg_package_lpa', 'N/A')} LPA | Highest: ₹{p.get('highest_package_lpa', 'N/A')} LPA")
                lines.append(f"    Placement Rate: {p.get('placement_percentage', 'N/A')}%")
                recruiters = p.get('top_recruiters', 'Various')
                if recruiters and len(recruiters) > 60:
                    recruiters = recruiters[:60] + '...'
                lines.append(f"    Top Recruiters: {recruiters}")
        
        facilities = college_info_service.get_facilities(college_code)
        if facilities:
            lines.append(f"\n**Campus Facilities:**")
            lines.append(f"Campus Area: {facilities.get('campus_area', 'N/A')} acres")
            lines.append(f"Hostels: {facilities.get('hostel_boys', '0')} (Boys), {facilities.get('hostel_girls', '0')} (Girls)")
            lines.append(f"Hostel Capacity: {facilities.get('hostel_capacity', 'N/A')}")
            lines.append(f"Library Books: {facilities.get('library_books', 'N/A')}")
            lines.append(f"Computer Labs: {facilities.get('computer_labs', 'N/A')}")
            lines.append(f"Sports: {facilities.get('sports', 'Available')}")
            if facilities.get('wifi') == 'Yes':
                lines.append("Wi-Fi: Available throughout campus")
            if facilities.get('gym') == 'Yes':
                lines.append("Gym: Available")
            if facilities.get('medical') == 'Yes':
                lines.append("Medical Facility: Available")
        
        seat_matrix = college_info_service.get_seat_matrix(college_code)
        if seat_matrix:
            lines.append(f"\n**Seat Matrix (Branch-wise):**")
            for branch, seats in list(seat_matrix.items())[:5]:
                lines.append(f"  {branch}: {seats.get('total_seats', 'N/A')} seats")
        
        lines.append(f"\n=== INSTRUCTIONS ===")
        lines.append("Use the above data to answer the user's question BECOME SPECIFIC.")
        lines.append("Quote exact figures from the data. Be helpful and informative.")
        
        return "\n".join(lines)
    
    def _get_off_topic_response(self, query: str) -> str:
        import random
        if self._is_greeting(query):
            return random.choice(GREETING_RESPONSES)
        return random.choice(OFF_TOPIC_RESPONSES)
    
    def _is_multi_exam_query(self, query: str) -> bool:
        query_lower = query.lower()
        has_cee = bool(re.search(r'cee', query_lower))
        has_jee = bool(re.search(r'jee', query_lower))
        return has_cee and has_jee
    
    def _process_multi_exam_query(self, query: str) -> Dict[str, Any]:
        parsed_queries = self.parser.parse_multi_exam(query)
        exam_results = self.retriever.retrieve_multi_exam(parsed_queries)
        
        all_colleges = []
        context_parts = []
        
        for exam, docs in exam_results.items():
            if docs:
                colleges_for_exam = self.context_builder.format_for_display(docs)
                all_colleges.extend(colleges_for_exam)
                
                college_names = set(c["college_name"] for c in colleges_for_exam)
                context_parts.append(f"=== {exam.upper()} RESULTS (MATCHING COLLEGES) ===")
                context_parts.append(f"User {exam} rank: {[pq.rank for pq in parsed_queries if pq.exam == exam][0]}")
                context_parts.append(f"Available colleges: {', '.join(college_names)}")
                context_parts.append("ONLY MENTION THESE COLLEGES FOR THIS EXAM.\n")
                
                for i, doc in enumerate(docs[:10], 1):
                    metadata = doc.get("metadata", {})
                    match = doc.get("match_percentage", 0)
                    context_parts.append(f"{i}. {metadata.get('college_name', 'Unknown')} - {metadata.get('branch', 'N/A')}")
                    context_parts.append(f"   Category: {metadata.get('category', 'General')}, Closing Rank: {metadata.get('closing_rank', 'N/A')}, Match: {match:.1f}%")
                context_parts.append("")
        
        context_parts.append("=== RESPONSE INSTRUCTIONS ===")
        context_parts.append("Show results for BOTH CEE and JEE separately.")
        context_parts.append("Label which colleges are for CEE and which are for JEE.")
        context_parts.append("Do NOT mix them up.")
        
        return {
            "parsed_query": parsed_queries[0] if parsed_queries else ParsedQuery(
                intent="college_prediction",
                exam="Both",
                rank=None,
                category="General",
                branch=None,
                raw_query=query
            ),
            "context": "\n".join(context_parts),
            "colleges": all_colleges,
            "doc_count": len(all_colleges),
            "is_off_topic": False,
            "is_multi_exam": True
        }
    
    async def process_query(
        self,
        query: str,
        history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        if self._is_greeting(query):
            return {
                "parsed_query": ParsedQuery(
                    intent="greeting",
                    exam=None,
                    rank=None,
                    category="General",
                    branch=None,
                    raw_query=query
                ),
                "context": self._get_off_topic_response(query),
                "colleges": [],
                "doc_count": 0,
                "is_off_topic": True
            }
        
        if self._is_off_topic(query):
            return {
                "parsed_query": ParsedQuery(
                    intent="off_topic",
                    exam=None,
                    rank=None,
                    category="General",
                    branch=None,
                    raw_query=query
                ),
                "context": self._get_off_topic_response(query),
                "colleges": [],
                "doc_count": 0,
                "is_off_topic": True
            }
        
        if self._is_multi_exam_query(query):
            return self._process_multi_exam_query(query)
        
        college_code, is_info_query = self._is_college_info_query(query)
        if is_info_query:
            from app.services.college_info_service import college_info_service
            college_info = college_info_service.get_college_info(college_code)
            
            return {
                "parsed_query": ParsedQuery(
                    intent="college_info",
                    exam=None,
                    rank=None,
                    category="General",
                    branch=None,
                    raw_query=query,
                    college_code=college_code
                ),
                "context": self._build_college_info_context(college_code, query),
                "colleges": [],
                "doc_count": 0,
                "is_off_topic": False,
                "is_info_query": True
            }
        
        parsed = self.parser.parse(query)
        
        docs = self.retriever.retrieve(parsed)
        
        context = self.context_builder.build(parsed, docs)
        
        colleges = self.context_builder.format_for_display(docs)
        
        return {
            "parsed_query": parsed,
            "context": context,
            "colleges": colleges,
            "doc_count": len(docs),
            "is_off_topic": False
        }
    
    async def generate_response_stream(
        self,
        query: str,
        history: List[Dict[str, str]] = None
    ) -> AsyncIterator[str]:
        processed = await self.process_query(query, history)
        
        if processed.get("is_off_topic"):
            yield processed["context"]
            return
        
        if processed.get("is_info_query"):
            context = processed["context"]
        else:
            context = processed["context"]
        
        async for token in self.llm.generate_stream(
            context=context,
            query=query,
            history=history
        ):
            yield token
    
    def generate_response_sync(
        self,
        query: str,
        history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        import asyncio
        
        processed = asyncio.run(self.process_query(query, history))
        
        if processed.get("is_off_topic"):
            return {
                "response": processed["context"],
                "colleges": [],
                "parsed_query": processed["parsed_query"].dict()
            }
        
        response = self.llm.generate_sync(
            context=processed["context"],
            query=query,
            history=history
        )
        
        return {
            "response": response,
            "colleges": processed["colleges"],
            "parsed_query": processed["parsed_query"].dict()
        }
    
    def get_colleges_by_rank(
        self,
        rank: int,
        category: str = "General",
        exam: str = "CEE",
        branch: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        parsed = ParsedQuery(
            intent="college_prediction",
            exam=exam,
            rank=rank,
            category=category,
            branch=branch,
            raw_query=f"Rank {rank} in {exam}"
        )
        
        docs = self.retriever.retrieve(parsed, max_results=limit)
        
        return self.context_builder.format_for_display(docs)


rag_pipeline = RAGPipeline()
