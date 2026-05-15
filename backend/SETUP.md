# Backend Setup Complete

## Quick Start

### 1. Install Dependencies
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 3. Ingest Data
```bash
python scripts/ingest_data.py
```

### 4. Run the Server
```bash
python run.py
```

Server will start at `http://localhost:8000`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Chat with streamed response |
| `/api/colleges` | GET | Get colleges by rank |
| `/api/health` | GET | Health check |

## Project Structure
```
backend/
├── app/
│   ├── api/           # API routes
│   ├── core/          # Core RAG components
│   ├── models/        # Pydantic models
│   ├── services/      # Business logic
│   └── utils/         # Utilities
├── data/              # CSV data files
├── scripts/           # Ingestion scripts
└── tests/             # Test files
```
