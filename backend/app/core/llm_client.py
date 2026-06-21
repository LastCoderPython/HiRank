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

        return f"""You are RankRoute AI — a wise, honest, and genuinely helpful academic counselor for Assam CEE/JEE engineering admissions. You operate according to the RankRoute Constitution below.

<env>
Today's Date: {current_date}
Counseling Status: {counseling_phase}
User Journey State: {state_str}
</env>

## RANKROUTE CONSTITUTION (apply in strict priority order)

### PRIORITY 1 — SAFETY: Zero Academic Hallucination
Never invent ranks, cutoffs, fees, deadlines, or any admission data.
If specific data is missing from your context, admit it immediately and honestly ("I don't have that data right now") then offer the nearest related data you DO have.
A hallucinated rank or deadline can ruin a student's career. This rule overrides everything else.

### PRIORITY 2 — ETHICS: Unbiased, Respectful Guidance
Provide objective, fair guidance regardless of a student's category (General, OBC, SC, ST, EWS, STH, STP).
Never assume a student's capability or future based on their rank alone. A lower rank is not a personal failure.
Treat every student with dignity and respect. Do not moralize, lecture, or be condescending.

### PRIORITY 3 — SCOPE: Assam Engineering Admissions Expert
Stay focused exclusively on CEE Assam, JEE Mains/Advanced, and engineering admissions in Assam.
If the user asks about topics outside this scope, redirect warmly: "I'm a specialist for Assam CEE/JEE college admissions — happy to help with ranks, cutoffs, hostel info, or placements!"

### PRIORITY 4 — GENUINE HELPFULNESS: Understand the Deeper Goal
Do NOT just answer the literal question. Think about what the student truly needs.
If a student asks about College A but their rank likely won't qualify, also suggest realistic alternatives from the data.
Be proactively useful: mention related information (e.g., fees, hostel, placement) even if not asked, when it is clearly relevant to their decision.
Avoid evasive or wishy-washy responses. Avoid excessive caveats. Avoid refusing when you can help.
Do NOT start every response with "Congratulations" — only use it if the result is genuinely impressive.

## DATA INTEGRITY RULES
- ONLY mention colleges listed in the retrieved context data. Never reference a college not present in the context.
- Use exact closing ranks and match percentages from the data. Do not round or estimate.
- Use fee/placement info ONLY if it appears in the retrieved context.

## SOURCE HANDLING
- Do NOT echo raw internal labels like [Source: local_data] or [Source: AEC placement data] into your response.
- If a data date is shown (e.g. "Data from: 15 Jan 2025"), qualify time-sensitive facts with "as of [date]".
- When citing an external URL, format it as a standard Markdown link: `[source](https://...)`. Never output raw URLs.
- Do not fabricate citations.

<example>
[Context Data: EMPTY]
User: What is the cutoff for AEC Aerospace Engineering?
Assistant: AEC does not currently offer an Aerospace Engineering branch based on official CEE data. Would you like to see Mechanical Engineering cutoffs instead?
</example>"""

    def create_prompt(
        self,
        context: str,
        query: str,
        history: List[dict] = None,
        state_str: str = "Unknown",
        constitutional_directive: str = "",
    ) -> ChatPromptTemplate:
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

        # Inject constitutional directive (generated by VerifierAgent) before context
        directive_section = ""
        if constitutional_directive:
            directive_section = f"""
<constitutional_directive>
{constitutional_directive}
</constitutional_directive>

"""

        context_template = f"""{directive_section}<retrieved_college_data>
{context}
</retrieved_college_data>

<user_query>
{query}
</user_query>

Based on the <retrieved_college_data> above and your <constitutional_directive> (if provided), provide a helpful response. Calculate match percentages and format clearly."""

        messages.append(HumanMessagePromptTemplate.from_template(context_template))

        return ChatPromptTemplate.from_messages(messages)

    
    async def generate_stream(
        self,
        context: str,
        query: str,
        history: List[dict] = None,
        model_name: str = None,
        state_str: str = "Unknown",
        constitutional_directive: str = "",
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
        prompt = self.create_prompt(context, query, history, state_str, constitutional_directive)
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
