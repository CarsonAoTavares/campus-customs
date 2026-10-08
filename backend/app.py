from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / 'data' / 'campus_customs.db'
PRODUCTS_DIR = BASE_DIR / 'data' / 'products'
load_dotenv(BASE_DIR / '.env')

app = FastAPI(title='Campus Customs API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

SYSTEM_PROMPT = """
You are the Campus Customs shopping assistant.
Use the supplied product context from the local database and never invent facts.
If the user asks about pricing, availability, or product matches, cite the exact prices and stock information from the context.
When recommending products, list only products that appear in the provided product context.
Keep responses concise, clear, and helpful for a Yale-focused customer.
"""


class RegisterPayload(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class ChatPayload(BaseModel):
    message: str


class LoginPayload(BaseModel):
    email: str
    password: str


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    iterations = 600_000
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
    return f'pbkdf2_sha256${iterations}${salt}${digest.hex()}'


def verify_password(password: str, stored_hash: str) -> bool:
    parts = stored_hash.split('$')
    if len(parts) == 3:
        algorithm, salt, expected_hex = parts
        iterations = 120_000
    elif len(parts) == 4:
        algorithm, raw_iterations, salt, expected_hex = parts
        try:
            iterations = int(raw_iterations)
        except ValueError:
            return False
        if not 1 <= iterations <= 2_000_000:
            return False
    else:
        return False
    if algorithm != 'pbkdf2_sha256':
        return False
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
    return hmac.compare_digest(digest.hex(), expected_hex)


def normalize_product(raw: sqlite3.Row) -> dict:
    colors = json.loads(raw['colors']) if raw['colors'] else []
    searchable = json.loads(raw['search_tags']) if raw['search_tags'] else []
    inventory = []
    total_quantity = 0
    with get_db_connection() as conn:
        rows = conn.execute(
            'SELECT size, quantity FROM inventory WHERE product_id = ? ORDER BY size',
            (raw['product_id'],),
        ).fetchall()
        for row in rows:
            total_quantity += int(row['quantity'])
            inventory.append({'size': row['size'], 'quantity': int(row['quantity'])})

    return {
        'product_id': raw['product_id'],
        'name': raw['name'],
        'garment_type': raw['garment_type'],
        'description': raw['description'],
        'colors': colors,
        'search_tags': searchable,
        'price': float(raw['price']),
        'image_url': f"/api/images/{raw['image_file_path']}",
        'inventory': inventory,
        'total_inventory': total_quantity,
        'available_sizes': [item['size'] for item in inventory if item['quantity'] > 0],
    }


def search_products_for_prompt(message: str, limit: int = 4) -> list[dict]:
    cleaned = re.sub(r'[^a-z0-9\s]', ' ', message.lower())
    tokens = [token for token in cleaned.split() if token]
    if not tokens:
        tokens = ['yale']

    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM catalogue ORDER BY name').fetchall()

    matches: list[dict] = []
    for row in rows:
        haystack = ' '.join([
            row['name'] or '',
            row['garment_type'] or '',
            row['description'] or '',
            row['colors'] or '',
            row['search_tags'] or '',
        ]).lower()
        if any(token in haystack for token in tokens):
            matches.append(normalize_product(row))

    if len(matches) < limit:
        for row in rows:
            if all(product['product_id'] != row['product_id'] for product in matches):
                matches.append(normalize_product(row))
                if len(matches) >= limit:
                    break

    return matches[:limit]


def product_context_text(products: list[dict]) -> str:
    if not products:
        return 'No products matched the user query in the local database.'

    lines = []
    for product in products:
        sizes = ', '.join(f'{item["size"]}:{item["quantity"]}' for item in product['inventory']) if product['inventory'] else 'no inventory listed'
        lines.append(
            f"- {product['name']} | {product['garment_type']} | ${product['price']:.2f} | stock: {sizes}"
        )
    return '\n'.join(lines)


def build_agent():
    api_key = os.getenv('PORTKEY_API_KEY')
    if not api_key:
        return None
    provider = OpenAIProvider(api_key=api_key, base_url='https://ai.portkey.ai/v1')
    model = OpenAIChatModel('gpt-5', provider=provider)
    return Agent(model, system_prompt=SYSTEM_PROMPT)


AGENT = build_agent()


def fallback_answer(message: str, products: list[dict]) -> str:
    if not products:
        return 'I could not find a close product match in the Campus Customs catalog. Try a more specific item like hoodie, Yale crewneck, or Harvard rivalry tee.'

    product_names = ', '.join(product['name'] for product in products)
    first = products[0]
    if 'hoodie' in message.lower():
        return (
            f"I found a few strong matches: {product_names}. The best fit is {first['name']} at ${first['price']:.2f}. "
            f"It currently has {first['total_inventory']} total units in stock across sizes {', '.join(first['available_sizes']) or 'no sizes in stock'}."
        )
    return (
        f"Based on your question, these are the most relevant items: {product_names}. "
        f"The first option is {first['name']} at ${first['price']:.2f}, with available sizes {', '.join(first['available_sizes']) or 'currently unavailable'}."
    )


@app.get('/api/health')
def health() -> dict:
    return {'status': 'healthy'}


@app.get('/api/products')
def list_products(search: str = '') -> dict:
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM catalogue ORDER BY name').fetchall()

    products = [normalize_product(row) for row in rows]
    if search:
        term = search.lower()
        products = [
            product for product in products
            if term in ' '.join([
                product['name'],
                product['garment_type'],
                product['description'],
                ' '.join(product['colors']),
                ' '.join(product['search_tags']),
            ]).lower()
        ]

    return {'products': products[:12]}


@app.get('/api/images/{image_path:path}')
def serve_image(image_path: str) -> FileResponse:
    file_path = PRODUCTS_DIR / image_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail='Image not found')
    return FileResponse(file_path)


@app.post('/api/register')
def register(payload: RegisterPayload) -> dict:
    email = payload.email.strip().lower()
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    if not (first_name and last_name and email and payload.password):
        raise HTTPException(status_code=400, detail='All fields are required.')
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        raise HTTPException(status_code=400, detail='Enter a valid email address.')

    with get_db_connection() as conn:
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail='An account with that email already exists.')

        password_hash = hash_password(payload.password)
        conn.execute(
            'INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)',
            (f'{first_name} {last_name}', email, password_hash, first_name, last_name),
        )
        conn.commit()

    return {
        'message': 'Account created successfully.',
        'user': {
            'name': f'{first_name} {last_name}',
            'email': email,
        },
    }


@app.post('/api/login')
def login(payload: LoginPayload) -> dict:
    email = payload.email.strip().lower()
    with get_db_connection() as conn:
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail='Invalid email or password.')
        if not verify_password(payload.password, user['password_hash']):
            raise HTTPException(status_code=401, detail='Invalid email or password.')

    return {
        'message': 'Login successful.',
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
        },
    }


@app.post('/api/chat')
def chat(payload: ChatPayload) -> dict:
    message = (payload.message or '').strip()
    if not message:
        raise HTTPException(status_code=400, detail='A message is required.')

    products = search_products_for_prompt(message, limit=4)
    context = product_context_text(products)

    if AGENT is None:
        answer = fallback_answer(message, products)
        return {'answer': answer, 'related_products': products}

    final = AGENT.run_sync(
        f"USER QUESTION: {message}\n\nPRODUCT CONTEXT FROM LOCAL DATABASE:\n{context}\n\n"
        'Return a helpful answer using only the product context above. Mention exact products, prices, and stock details when available.'
    )
    answer = str(final.output).strip()
    return {'answer': answer, 'related_products': products}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run('backend.app:app', host='0.0.0.0', port=8000, reload=True)
