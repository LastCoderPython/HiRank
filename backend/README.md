# RankRoute CEE Rank Predictor - Technical Documentation

## Overview

RankRoute is an AI-powered admission counseling system for Assam CEE and JEE Mains students. It uses RAG (Retrieval-Augmented Generation) to provide accurate college predictions based on historical cutoff data.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Chat UI    │  │  Sidebar    │  │  Settings/College Cards  │ │
│  │  (Black/   │  │  (Recent    │  │  (View Details Modal)    │ │
│  │   White)   │  │   Chats)    │  │                          │ │
│  └──────┬──────┘  └──────┬──────┘  └────────────┬─────────────┘ │
└─────────┼────────────────┼─────────────────────┼───────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API GATEWAY (FastAPI)                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  POST /api/chat                                            │ │
│  │  - Accepts: {message, history, session_id}                │ │
│  │  - Returns: SSE Stream (token-by-token response)          │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  GET /api/colleges?rank=3000&category=General            │ │
│  │  - Returns: List of eligible colleges with match %        │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RAG PIPELINE                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Query       │─▶│  Parameter   │─▶│  Metadata Filter    │  │
│  │  Router      │  │  Extraction  │  │  (ChromaDB)         │  │
│  └──────────────┘  └──────────────┘  └──────────┬───────────┘  │
│                                                  │              │
│                                                  ▼              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    CONTEXT ASSEMBLY                       │  │
│  │  - Top 10 matching colleges                              │  │
│  │  - Historical trends                                      │  │
│  │  - Category-wise cutoffs                                  │  │
│  └──────────────────────────────┬───────────────────────────┘  │
│                                 │                              │
│                                 ▼                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              LLM GENERATION (Gemini/OpenAI)              │  │
│  │  System Prompt: "Expert admission counselor for CEE..."  │  │
│  │  + Retrieved Context + User Query                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  CSV Files   │  │  ChromaDB    │  │  Metadata Store    │  │
│  │  (CEE Cut-  │  │  (Vector    │  │  (College info,    │  │
│  │   offs)      │  │   Store)    │  │   placements)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Data Ingestion Pipeline

```
CSV File → Pandas DataFrame → Text Chunks → Embeddings → ChromaDB
```

**Input CSV Format:**
```csv
College_Name,Branch,Category,Opening_Rank,Closing_Rank,Year
AEC,Computer Science,General,450,1200,2023
AEC,Computer Science,General,400,1100,2022
AEC,Mechanical,General,2800,3250,2023
```

**Text Chunk Generation:**
```python
# Each row becomes a searchable text chunk
chunk = f"At {row['College_Name']}, the {row['Branch']} branch 
         for {row['Category']} category had opening rank of 
         {row['Opening_Rank']} and closing rank of {row['Closing_Rank']} 
         in year {row['Year']}."
```

**Metadata Structure:**
```python
metadata = {
    "college": "AEC",
    "college_full": "Assam Engineering College",
    "branch": "Computer Science",
    "category": "General",
    "opening_rank": 450,
    "closing_rank": 1200,
    "year": 2023,
    "source": "CEE"
}
```

### 2. Query Processing Pipeline

```
User Query → Intent Extraction → Parameter Parsing → 
Database Query → Context Assembly → LLM Response → SSE Stream
```

**Example Flow:**

```
Input: "My rank is 3000 in CEE, which college can I get?"

Step 1: Intent Extraction
{
  "intent": "college_prediction",
  "exam": "CEE",
  "rank": 3000,
  "category": "General",
  "branch_preference": null
}

Step 2: Database Query
SELECT * FROM cutoffs 
WHERE closing_rank >= 2800 AND closing_rank <= 3500
AND category = 'General'
ORDER BY closing_rank ASC
LIMIT 10

Step 3: Context Assembly
- AEC Mechanical (Closing: 3250) ✓ Match
- JEC Computer Science (Closing: 3400) ✓ Match
- GUIST Electronics (Closing: 3100) ✓ Match
- ... (7 more results)

Step 4: LLM Generation
System: "You are an expert CEE admission counselor...
         Based on the retrieved data, suggest colleges..."

Response: "Based on your rank of 3000 in CEE, here are 
           the colleges you have a good chance of getting..."
```

---

## API Endpoints

### POST /api/chat
Main chat endpoint with streaming response.

**Request:**
```json
{
  "message": "My rank is 3000 in CEE",
  "session_id": "optional-session-id",
  "history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ]
}
```

**Response:** SSE Stream
```
data: {"token": "Based"}
data: {"token": " on"}
data: {"token": " your"}
data: {"token": " rank"}
...
data: [DONE]
```

### GET /api/colleges
Get filtered college list.

**Query Parameters:**
- `rank`: User's rank (required)
- `category`: General/OBC/SC/ST (default: General)
- `branch`: Optional branch filter
- `limit`: Max results (default: 10)

**Response:**
```json
{
  "colleges": [
    {
      "name": "Assam Engineering College",
      "branch": "Mechanical Engineering",
      "closing_rank": 3250,
      "match_percentage": 92,
      "category": "General"
    }
  ],
  "total": 5
}
```

---

## Vector Database Schema

### Collections

#### cee_cutoffs
```python
{
    "id": "uuid",
    "embedding": [768 floats],  # from text-embedding-004
    "metadata": {
        "college_code": "AEC",
        "college_name": "Assam Engineering College",
        "branch": "Computer Science",
        "category": "General",
        "opening_rank": 450,
        "closing_rank": 1200,
        "year": 2023,
        "source": "CEE",
        "seat_type": "Government"
    },
    "document": "At Assam Engineering College (AEC)..."
}
```

#### jee_cutoffs
```python
{
    "id": "uuid",
    "embedding": [768 floats],
    "metadata": {
        "institute": "NIT Silchar",
        "branch": "Computer Science",
        "category": "General",
        "opening_rank": 5000,
        "closing_rank": 12000,
        "year": 2023,
        "source": "JOSAA",
        "quota": "Home State"
    },
    "document": "At NIT Silchar..."
}
```

---

## System Prompts

### CEE Counselor Persona
```
You are an expert admission counselor specializing in Assam CEE 
(Combined Entrance Examination). You have comprehensive knowledge 
of all engineering colleges in Assam and their historical cut-offs.

Your role:
1. Analyze student ranks and predict college admissions
2. Provide realistic expectations based on historical data
3. Suggest backup options and alternative branches
4. Offer guidance on course selection and career paths
5. Answer questions about colleges, placements, and facilities

Guidelines:
- Always base predictions on retrieved cutoff data
- Be encouraging but realistic with predictions
- Show match percentage for each recommendation
- If rank is borderline, mention it clearly
- Recommend nearby ranks for safety margin
- Format responses with clear bullet points
- Cite the year of cutoff data used

Important:
- Never make up cutoff numbers
- If data is insufficient, say so honestly
- For vague queries, ask clarifying questions
```

---

## Environment Variables

```env
# .env file

# LLM Configuration
LLM_PROVIDER=google  # google, openai, or ollama
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key  # if using OpenAI

# Embedding Model
EMBEDDING_MODEL=text-embedding-004  # Google's embedding model
# or
EMBEDDING_MODEL=text-embedding-3-small  # OpenAI

# Vector Database
VECTOR_DB=chroma  # chroma or qdrant
CHROMA_PERSIST_DIR=./data/chroma
QDRANT_URL=http://localhost:6333

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000

# Data Paths
CEE_DATA_PATH=./data/cee_cutoffs.csv
JEE_DATA_PATH=./data/jee_cutoffs.csv
```

---

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Settings and environment
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py         # Chat endpoint
│   │   │   └── colleges.py     # College listing endpoint
│   │   └── dependencies.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── rag_pipeline.py     # Main RAG orchestration
│   │   ├── embeddings.py       # Embedding generation
│   │   └── llm_client.py       # LLM interface
│   ├── services/
│   │   ├── __init__.py
│   │   ├── query_parser.py     # Intent & parameter extraction
│   │   ├── retriever.py        # Vector DB retrieval
│   │   └── context_builder.py # Context assembly
│   ├── models/
│   │   ├── __init__.py
│   │   ├── requests.py         # Pydantic request models
│   │   ├── responses.py        # Pydantic response models
│   │   └── schemas.py         # Database schemas
│   └── utils/
│       ├── __init__.py
│       ├── chunking.py         # Text chunking utilities
│       └── helpers.py
├── data/
│   ├── cee_cutoffs.csv
│   ├── jee_cutoffs.csv
│   └── chroma/                  # Vector DB persistence
├── scripts/
│   ├── ingest_data.py          # Data ingestion script
│   └── test_rag.py             # RAG testing script
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

---

## Next Steps

1. Implement data ingestion pipeline
2. Set up ChromaDB and create collections
3. Build the RAG retrieval system
4. Integrate LLM (Gemini/OpenAI)
5. Create FastAPI endpoints with SSE streaming
6. Connect frontend to backend API
