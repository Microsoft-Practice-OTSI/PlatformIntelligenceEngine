# ADPIE - Platform Intelligence Engine

## Quick Start

### Backend (FastAPI)

```bash
cd d:\Gravity\ADPIE
uvicorn pie.api.app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### Frontend (React + Vite)

```bash
cd d:\Gravity\ADPIE\frontend
npm run dev
```

The frontend will be available at `http://localhost:5173` (default Vite port)

## Project Structure

```
ADPIE/
├── src/pie/           # Backend source code
│   ├── api/           # FastAPI application
│   ├── auth/          # Authentication modules
│   ├── teams/         # Teams integration
│   └── ...
├── frontend/          # React frontend
│   ├── src/
│   └── ...
├── tests/             # Test suite
├── Documentation/     # Project documentation
└── spikes/            # Experimental spikes
```

## Requirements

- Python 3.11+
- Node.js 18+
- uv or pip for Python dependencies
- npm for Node dependencies

## Install Dependencies

### Backend
```bash
cd d:\Gravity\ADPIE
pip install -r requirements.txt
# or with uv
uv pip install -r requirements.txt
```

### Frontend
```bash
cd d:\Gravity\ADPIE\frontend
npm install
```