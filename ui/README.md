# Stock Weather AI - UI

This is a small React + TypeScript + Vite + Tailwind frontend to consume the FastAPI `/reports` endpoint from the parent project.

Quick start:

1. Install dependencies

```
cd ui
npm install
```

2. Start the FastAPI backend (from project root):

```
uvicorn api:app --reload --port 8000
```

3. Start the UI

```
cd ui
npm run dev
```

If your API is not at http://localhost:8000 set VITE_API_BASE in `.env`.
