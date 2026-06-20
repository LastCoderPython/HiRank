from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.config import settings
from typing import Optional, List, AsyncIterator
import logging
import threading

logger = logging.getLogger(__name__)


class LLMClient:
    _instance: Optional['LLMClient'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._lock = threading.Lock()
        return cls._instance
    
    def __init__(self):
        pass
    
    def ensure_initialized(self):
        """Eagerly initialize all LLM models. Double-checked locking."""
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            self._initialize_llm()
            self._initialized = True
    
    def _initialize_llm(self):
        self.llms = {}
        
        api_key = settings.groq_api_key
        if not api_key:
            logger.warning("GROQ_API_KEY not set - LLM will not be initialized during import")
            return
        
        for model_name in settings.model_order:
            try:
                self.llms[model_name] = ChatGroq(
                    model=model_name,
                    groq_api_key=api_key,
                    temperature=0.7,
                    streaming=True,
                    max_tokens=2048
                )
                logger.info(f"Initialized model: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize {model_name}: {e}")
        
        if self.llms and settings.model_order:
            self.primary_model = settings.primary_model
            logger.info(f"Primary model set to: {self.primary_model}")
    
    def get_system_prompt(self, state_str: str = "Unknown") -> str:
        from datetime import datetime
        import os
        
        current_date = datetime.now().strftime("%B %d, %Y")
        counseling_phase = os.getenv("COUNSELING_PHASE", "Preparation Phase")
        
        return f"""You are RankRoute AI for Assam CEE/JEE admissions.

<env>
Today's Date: {current_date}
Counseling Status: {counseling_phase}
User Journey State: {state_str}
</env>

CRITICAL RULE - ONLY USE COLLEGES FROM THE CONTEXT DATA:
- You MUST ONLY mention colleges that are listed in the "ELIGIBLE COLLEGES" section
- NEVER mention any college that is NOT in the retrieved data
- If a college is not in the data, do NOT talk about it
- Double-check: only colleges from the context can be mentioned

When showing college recommendations:
1. List ONLY colleges from the context data
2. Include the exact match percentage shown
3. Include exact closing rank from the data
4. Use fee/placement info ONLY if provided in the context

RESPONSE FORMAT:
- Open with a warm, contextually appropriate sentence based on what the user actually asked (do NOT start every response with "Congratulations" — only use it if the user has just shared a genuinely impressive result)
- List the matching colleges from the data (name, branch, closing rank, match %)
- Keep response concise. Be helpful and encouraging.
- Never invent data. If information is not in the context, say so honestly.

SOURCE HANDLING:
- Do NOT echo internal labels like [Source: local_data], [Source: AEC placement data], or similar raw tags into your response
- If a data date is provided (e.g. "Data from: 15 Jan 2025"), qualify time-sensitive facts with "as of [date]"
- When citing an external URL, you MUST format it as a standard Markdown link (e.g., `[source](https://...)`). Do not output raw, unformatted URLs in plain text.
- Do not make up source citations

REFUSAL POLICY:
- If the user asks about non-Assam Engineering topics (recipes, sports, general knowledge, etc.), respond warmly: "I'm a specialist for Assam CEE/JEE college admissions — happy to help with ranks, cutoffs, hostel info, or placements! Is there anything along those lines I can assist with?"

<example>
[Context Data: EMPTY]
User: What is the cutoff for AEC Aerospace Engineering?
Assistant: AEC does not currently offer an Aerospace Engineering branch based on official CEE data. Would you like to see Mechanical Engineering cutoffs instead?
</example>"""
    
    def create_prompt(self, context: str, query: str, history: List[dict] = None, state_str: str = "Unknown") -> ChatPromptTemplate:
        system_prompt = self.get_system_prompt(state_str)
        
        messages = [
            SystemMessagePromptTemplate.from_template(system_prompt),
        ]
        
        if history:
            for msg in history[-4:]:
                if msg["role"] == "user":
                    messages.append(HumanMessagePromptTemplate.from_template(msg["content"]))
                else:
                    messages.append(SystemMessagePromptTemplate.from_template(msg["content"]))
        
        context_template = f"""
<retrieved_college_data>
{context}
</retrieved_college_data>

<user_query>
{query}
</user_query>

Based on the <retrieved_college_data> above, provide a helpful response. Calculate match percentages and format clearly."""
        
        messages.append(HumanMessagePromptTemplate.from_template(context_template))
        
        return ChatPromptTemplate.from_messages(messages)
    
    async def generate_stream(
        self, 
        context: str, 
        query: str, 
        history: List[dict] = None,
        model_name: str = None,
        state_str: str = "Unknown"
    ) -> AsyncIterator[str]:
        self.ensure_initialized()
        if not self.llms:
            raise RuntimeError("LLM not initialized. Please set GROQ_API_KEY in .env file")
        
        model_to_use = model_name or self.primary_model
        
        for model in settings.model_order:
            if model in self.llms:
                model_to_use = model
                break
        
        if model_to_use not in self.llms:
            raise RuntimeError(f"Model {model_to_use} not available")
        
        llm = self.llms[model_to_use]
        prompt = self.create_prompt(context, query, history, state_str)
        chain = prompt | llm | StrOutputParser()
        
        try:
            async for chunk in chain.astream({}):
                yield chunk
        except Exception as e:
            logger.error(f"Error with model {model_to_use}: {e}")
            
            for fallback_model in settings.model_order:
                if fallback_model != model_to_use and fallback_model in self.llms:
                    logger.info(f"Falling back to {fallback_model}")
                    fallback_llm = self.llms[fallback_model]
                    chain = prompt | fallback_llm | StrOutputParser()
                    async for chunk in chain.astream({}):
                        yield chunk
                    return
            
            raise RuntimeError("All models failed")
    
    def generate_sync(self, context: str, query: str, history: List[dict] = None) -> str:
        self.ensure_initialized()
        if not self.llms:
            raise RuntimeError("LLM not initialized. Please set GROQ_API_KEY in .env file")
        
        for model_name in settings.model_order:
            if model_name not in self.llms:
                continue
            
            try:
                llm = self.llms[model_name]
                prompt = self.create_prompt(context, query, history)
                chain = prompt | llm | StrOutputParser()
                return chain.invoke({})
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}")
                continue
        
        raise RuntimeError("All models failed")


llm_client = LLMClient()
