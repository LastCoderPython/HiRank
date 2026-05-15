import re
from typing import Optional, Dict, Any
from app.models.requests import ParsedQuery


class QueryParser:
    def __init__(self):
        self.rank_patterns = [
            r"rank\s*(?:is|=|:)?\s*(\d+)",
            r"(\d+)\s*rank",
            r"got\s*(\d+)\s*(?:in|rank)",
            r"my\s*rank\s*(?:is|=|:)?\s*(\d+)",
            r"scored\s*(\d+)",
        ]
        
        self.percentile_patterns = [
            r"percentile\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*percentile",
            r"(\d+(?:\.\d+)?)\s*%ile",
        ]
        
        self.marks_patterns = [
            r"(\d+)\s*marks\s*(?:in\s*jee|in\s*jee\s*mains)?",
            r"marks\s*(?:is|=|:)?\s*(\d+)",
        ]
        
        self.category_patterns = {
            r"\b(general|gen|gm)\b": "General",
            r"\b(obc|other backward)\b": "OBC",
            r"\b(sc|scheduled caste)\b": "SC",
            r"\b(st|scheduled tribe)\b": "ST",
            r"\b(ews|economically weaker)\b": "EWS",
        }
        
        self.exam_patterns = {
            r"\bjee\s*mains?\b|jee\s*main|\bjee\b(?!\s*advanced)": "JEE",
            r"\bjee\s*advanced?\b": "JEE Advanced",
            r"\bcee\b|assam\s*cee|assam\s*combined": "CEE",
        }
        
        self.intent_patterns = {
            r"which\s*college|college\s*(?:can|will|could)\s*i\s*get": "college_prediction",
            r"cutoff|cut[\s-]?off|closing\s*rank": "cutoff_inquiry",
            r"branch|course|program": "branch_inquiry",
            r"compare|difference|vs": "comparison",
            r"placement|package|salary": "placement_inquiry",
            r"fee|fees|cost": "fee_inquiry",
        }
    
    def parse(self, query: str) -> ParsedQuery:
        query_lower = query.lower()
        
        exam = self._extract_exam(query_lower)
        rank = self._extract_rank(query, exam)
        category = self._extract_category(query_lower)
        branch = self._extract_branch(query_lower)
        intent = self._extract_intent(query_lower)
        
        return ParsedQuery(
            intent=intent,
            exam=exam,
            rank=rank,
            category=category or "General",
            branch=branch,
            raw_query=query
        )
    
    def parse_multi_exam(self, query: str) -> list:
        results = []
        query_lower = query.lower()
        category = self._extract_category(query_lower)
        
        cee_rank = self._extract_rank_for_exam(query, "CEE")
        if cee_rank:
            results.append(ParsedQuery(
                intent="college_prediction",
                exam="CEE",
                rank=cee_rank,
                category=category or "General",
                branch=None,
                raw_query=query
            ))
        
        jee_rank = self._extract_rank_for_exam(query, "JEE")
        if jee_rank:
            results.append(ParsedQuery(
                intent="college_prediction",
                exam="JEE",
                rank=jee_rank,
                category=category or "General",
                branch=None,
                raw_query=query
            ))
        
        if not results:
            results.append(self.parse(query))
        
        return results
    
    def _extract_rank_for_exam(self, query: str, exam: str) -> Optional[int]:
        query_lower = query.lower()
        
        if exam == "CEE":
            cee_patterns = [
                r"cee\s*rank\s*(?:is|=|:)?\s*(\d+)",
                r"(\d+)\s*(?:in|rank)\s*cee",
                r"rank\s*(\d+)\s*cee",
            ]
            for pattern in cee_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    return int(match.group(1))
        
        if exam == "JEE":
            jee_patterns = [
                r"jee\s*(?:mains?)?\s*rank\s*(?:is|=|:)?\s*(\d+)",
                r"(\d+)\s*(?:in|rank)\s*jee",
                r"rank\s*(\d+)\s*jee",
            ]
            for pattern in jee_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    return int(match.group(1))
            
            for pattern in self.percentile_patterns:
                if "jee" in query_lower:
                    match = re.search(pattern, query_lower)
                    if match:
                        percentile = float(match.group(1))
                        return self._percentile_to_rank(percentile)
            
            for pattern in self.marks_patterns:
                if "jee" in query_lower:
                    match = re.search(pattern, query_lower)
                    if match:
                        marks = int(match.group(1))
                        return self._marks_to_rank(marks)
        
        return None
    
    def _extract_rank(self, query: str, exam: str = None) -> Optional[int]:
        query_lower = query.lower()
        
        for pattern in self.rank_patterns:
            match = re.search(pattern, query_lower)
            if match:
                return int(match.group(1))
        
        if exam == "JEE" or "jee" in query_lower:
            for pattern in self.percentile_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    percentile = float(match.group(1))
                    return self._percentile_to_rank(percentile)
            
            for pattern in self.marks_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    marks = int(match.group(1))
                    return self._marks_to_rank(marks)
        
        numbers = re.findall(r'\b(\d{2,6})\b', query)
        if numbers:
            num = int(numbers[0])
            if 100 <= num <= 100000:
                if "rank" in query_lower or "score" in query_lower:
                    return num
                if num > 100 and num < 1000 and exam == "JEE":
                    return self._percentile_to_rank(num)
        
        return None
    
    def _percentile_to_rank(self, percentile: float) -> int:
        if percentile >= 99.9:
            return 100
        elif percentile >= 99.5:
            return 500
        elif percentile >= 99:
            return 1000
        elif percentile >= 98:
            return 2200
        elif percentile >= 97:
            return 3400
        elif percentile >= 96:
            return 4500
        elif percentile >= 95:
            return 5600
        elif percentile >= 90:
            return 11000
        elif percentile >= 85:
            return 17000
        elif percentile >= 80:
            return 24000
        elif percentile >= 75:
            return 32000
        elif percentile >= 70:
            return 40000
        elif percentile >= 60:
            return 60000
        elif percentile >= 50:
            return 85000
        else:
            return int(100000 - percentile * 1000)
    
    def _marks_to_rank(self, marks: int) -> int:
        if marks >= 280:
            return 100
        elif marks >= 250:
            return 500
        elif marks >= 220:
            return 1500
        elif marks >= 200:
            return 4000
        elif marks >= 180:
            return 10000
        elif marks >= 160:
            return 20000
        elif marks >= 140:
            return 35000
        elif marks >= 120:
            return 55000
        elif marks >= 100:
            return 80000
        elif marks >= 80:
            return 150000
        else:
            return 200000
    
    def _extract_category(self, query_lower: str) -> Optional[str]:
        for pattern, category in self.category_patterns.items():
            if re.search(pattern, query_lower):
                return category
        return None
    
    def _extract_exam(self, query_lower: str) -> Optional[str]:
        for pattern, exam in self.exam_patterns.items():
            if re.search(pattern, query_lower):
                return exam
        return None
    
    def _extract_branch(self, query_lower: str) -> Optional[str]:
        branch_keywords = {
            "computer science": "Computer Science",
            "cs": "Computer Science",
            "cse": "Computer Science",
            "electronics": "Electronics",
            "ece": "Electronics and Communication",
            "electrical": "Electrical",
            "mechanical": "Mechanical",
            "civil": "Civil",
            "information technology": "Information Technology",
            "it": "Information Technology",
            "chemical": "Chemical",
            "biotechnology": "Biotechnology",
        }
        
        for keyword, branch in branch_keywords.items():
            if keyword in query_lower:
                return branch
        return None
    
    def _extract_intent(self, query_lower: str) -> str:
        for pattern, intent in self.intent_patterns.items():
            if re.search(pattern, query_lower):
                return intent
        if "rank" in query_lower or "percentile" in query_lower or "jee" in query_lower:
            return "college_prediction"
        return "general_inquiry"
    
    def extract_parameters(self, query: str) -> Dict[str, Any]:
        parsed = self.parse(query)
        
        params = {
            "rank": parsed.rank,
            "category": parsed.category,
            "exam": parsed.exam,
            "branch": parsed.branch,
            "intent": parsed.intent,
        }
        
        if params["rank"] and params["exam"]:
            params["rank_buffer_low"] = max(100, int(params["rank"] * 0.1))
            params["rank_buffer_high"] = max(200, int(params["rank"] * 0.2))
        
        return params


query_parser = QueryParser()
