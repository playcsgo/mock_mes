# Line Monitor — 產線測試即時監控 demo

FastAPI + Uvicorn + MongoDB (PyMongo) + GraphQL (Strawberry) + WebSocket

## 啟動

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

打開 http://localhost:8000/health 與 http://localhost:8000/docs
