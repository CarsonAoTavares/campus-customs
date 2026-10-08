# Campus Customs

A Yale-themed merchandise storefront with a database-backed product catalog, per-size stock lookup, account registration/login, persistent chat for signed-in shoppers, and a PydanticAI shopping assistant.

## Local data pack

Keep the provided data pack local and do not commit it. Place it under the project root with this layout:

```text
hw4/
  data/
    campus_customs.db
    products/               # product image files referenced by catalogue.image_file_path
```

The database and image folder are excluded by `.gitignore`. The app expects the database tables `catalogue`, `inventory`, and `users` to match the supplied data pack.

## Environment

Create `.env` from `.env.example` and add a valid `PORTKEY_API_KEY` or `OPENAI_API_KEY`. Never commit `.env`. The model defaults to `gpt-5`; set `CAMPUS_CUSTOMS_MODEL` to override it.

## Run the backend

From the `hw4/` project root, create and activate a Python virtual environment and install the requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then start FastAPI from the backend directory with the required command:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API and interactive documentation are available at `http://127.0.0.1:8000` and `http://127.0.0.1:8000/docs`.

## Run the frontend

In a second terminal, from the `hw4/` project root:

```bash
cd frontend
npm ci
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). Vite proxies `/api` requests to FastAPI on port 8000, including product images and session-cookie requests.

## Project map

- `backend/main.py` exposes products, images, account, chat, and saved-history endpoints.
- `backend/agent.py`, `backend/tools.py`, `backend/models.py`, and `backend/prompts/prompt.md` compose the shopping agent, typed API contract, database tools, and safety instructions.
- `frontend/` contains the React + Vite + TypeScript storefront.
- `output/` contains the harness, design/usability notes, live-app checks, screenshots, and append-preserving audit trail.