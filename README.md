# Restv2 Full Application Run Guide

This repository contains two runnable systems that work together:

1. The enterprise target chatbot in [target_chatbot](target_chatbot)
2. The autonomous prompt-injection control plane and dashboard in [ai-redteam-framework](ai-redteam-framework) and [frontend](frontend)

The full user flow is:

- Start the target chatbot backend
- Start the red-team framework API
- Start the dashboard frontend
- Open the dashboard in the browser

---

## Project layout

- [target_chatbot](target_chatbot): FastAPI + business logic + SQLite target application used as the system under test
- [ai-redteam-framework](ai-redteam-framework): autonomous red-team framework that launches attacks and produces reports
- [frontend](frontend): Vite + React dashboard used to control the red-team framework

---

## Prerequisites

Before running the app, install:

- Python 3.10+
- Node.js 18+
- npm
- Ollama running locally
- A Qwen model available in Ollama, such as `qwen2.5:3b-instruct-q4_K_M`

Optional:

- OpenAI / Gemini / Groq API key if you want the framework to run against real LLM services

---

## 1. Start the target chatbot backend

From the workspace root:

```powershell
cd target_chatbot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

This starts the target application at:

- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/health

Make sure Ollama is running and that the configured model is already pulled.

---

## 2. Start the red-team framework API

Open a second terminal:

```powershell
cd ai-redteam-framework
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m api.app
```

This starts the dashboard API on:

- http://127.0.0.1:8080/
- http://127.0.0.1:8080/api/health

The Flask API serves the static frontend and exposes the red-team run endpoints.

---

## 3. Start the dashboard frontend

Open a third terminal:

```powershell
cd frontend
npm install
npm run dev
```

The Vite frontend will start on:

- http://127.0.0.1:5173

The frontend uses the API through the Vite proxy configured in [frontend/vite.config.ts](frontend/vite.config.ts), which forwards `/api` requests to the Flask backend on port `8080`.

---

## 4. Open the application

After all three services are running:

1. Visit http://127.0.0.1:5173
2. Use the dashboard to configure and launch an autonomous red-team run
3. The framework will call the target chatbot through its API endpoints

---

## 5. Run the framework from the CLI

If you want to run the red-team framework directly without using the dashboard, use the CLI from [ai-redteam-framework/main.py](ai-redteam-framework/main.py):

```powershell
cd ai-redteam-framework
python main.py --target mock --objective customer_support --max-iterations 15 --max-llm-calls 0
```

This is the offline/demo path and does not require a paid API setup.

For a real LLM-backed run, configure the provider environment variables before launching:

```powershell
$env:OPENAI_API_KEY = "your-key"
```

---

## 6. Common environment variables

The target chatbot reads settings from environment variables such as:

- `TARGET_MODE` (`vulnerable` or `hardened`)
- `OLLAMA_URL`
- `MODEL_NAME`
- `DB_PATH`
- `HOST`
- `PORT`

You can set them in the PowerShell session before starting the app.

---

## 7. Useful verification checks

After starting the services, verify the following:

- Target chatbot:

```powershell
curl http://127.0.0.1:8000/health
```

- Red-team API:

```powershell
curl http://127.0.0.1:8080/api/health
```

- Frontend dev server:

Open http://127.0.0.1:5173 in your browser.

---

## 8. Production note

This project is designed for local development and demo execution. The dashboard and backend are intended to be run together while the target chatbot remains available on the local network.

---

## 9. Troubleshooting

If the backend does not start:

- Confirm Python packages were installed in the active virtual environment
- Confirm the correct working directory
- Confirm Ollama is running and the model name matches the configured setting

If the frontend cannot reach the backend:

- Make sure the Flask API is still running on port `8080`
- Confirm the Vite proxy target in [frontend/vite.config.ts](frontend/vite.config.ts)

If the dashboard shows no responses:

- Start the red-team API first
- Confirm the target chatbot is healthy on `8000`
