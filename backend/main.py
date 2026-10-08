from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
import time

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic_ai import UsageLimits

try:
    from .audit import append_audit_event
    from .agent import agent
    from .models import ChatHistoryResponse, ChatRequest, ChatResponse, LoginRequest, ProductLookup, RegisterRequest, ShopperContext, StoredChatMessage
    from .tools import DB_PATH, get_db_connection, get_product_details, list_catalog_products, resolve_product_image, search_products
except ImportError:
    from audit import append_audit_event
    from agent import agent
    from models import ChatHistoryResponse, ChatRequest, ChatResponse, LoginRequest, ProductLookup, RegisterRequest, ShopperContext, StoredChatMessage
    from tools import DB_PATH, get_db_connection, get_product_details, list_catalog_products, resolve_product_image, search_products

logger = logging.getLogger(__name__)
app = FastAPI(title='Campus Customs API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_methods=['GET', 'POST'],
    allow_headers=['*'],
    allow_credentials=True,
)

SESSION_COOKIE = 'campus_customs_session'
SESSION_MAX_AGE = 60 * 60 * 24 * 30


def initialize_user_storage() -> None:
    if not DB_PATH.is_file():
        return
    with get_db_connection() as connection:
        connection.execute('PRAGMA foreign_keys = ON')
        connection.executescript(
            '''
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id_id
                ON chat_messages(user_id, id);
            '''
        )


initialize_user_storage()


def create_session(user_id: int, request: Request, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with get_db_connection() as connection:
        connection.execute('DELETE FROM auth_sessions WHERE expires_at <= ?', (int(time.time()),))
        connection.execute(
            'INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)',
            (token_hash, user_id, int(time.time()) + SESSION_MAX_AGE),
        )
        connection.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=request.url.scheme == 'https',
        samesite='lax',
        path='/',
    )


def current_user(request: Request) -> sqlite3.Row | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with get_db_connection() as connection:
        return connection.execute(
            '''SELECT users.id, users.name, users.email
               FROM auth_sessions JOIN users ON users.id = auth_sessions.user_id
               WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?''',
            (token_hash, int(time.time())),
        ).fetchone()


def read_chat_history(user_id: int, limit: int = 100) -> list[StoredChatMessage]:
    with get_db_connection() as connection:
        rows = connection.execute(
            'SELECT role, content, created_at FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?',
            (user_id, limit),
        ).fetchall()
    return [StoredChatMessage(**dict(row)) for row in reversed(rows)]


def store_chat_exchange(user_id: int, message: str, answer: str) -> None:
    with get_db_connection() as connection:
        connection.executemany(
            'INSERT INTO chat_messages (user_id, role, content) VALUES (?, ?, ?)',
            [(user_id, 'user', message), (user_id, 'assistant', answer)],
        )
        connection.commit()


def hash_password(password: str) -> str:
    iterations = 600_000
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations)
    return f'pbkdf2_sha256${iterations}${salt}${digest.hex()}'


def verify_password(password: str, stored_hash: str) -> bool:
    parts = stored_hash.split('$')
    if len(parts) == 3:
        algorithm, salt, expected = parts
        iterations = 120_000
    elif len(parts) == 4:
        algorithm, raw_iterations, salt, expected = parts
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
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations)
    return hmac.compare_digest(digest.hex(), expected)


def fallback_reply(products: list[ProductLookup], message: str = '') -> str:
    if not products:
        return 'I could not find a close match in the catalog. Try a product type such as hoodie, crewneck, or T-shirt.'
    asks_for_specifics = bool(re.search(r'\b(price|cost|stock|size|quantity|color|pink|red|blue|navy)\b', message, re.IGNORECASE))
    if len(products) > 1 and not asks_for_specifics:
        return f"I found {len(products)} matching pieces in the live catalog. Each card shows its image, description, and price; open one for exact stock by size."
    product = products[0]
    stock = ', '.join(
        f'{item.size}: {item.quantity} in stock' if item.in_stock else f'{item.size}: out of stock'
        for item in product.inventory
    ) or 'no stock information is listed'
    return f'{product.name} is ${product.price:.2f}. {product.description} Stock by size: {stock}.'


@app.get('/api/health')
def health() -> dict[str, str | bool]:
    return {'status': 'healthy', 'agent_configured': agent is not None}


@app.get('/api/products', response_model=dict[str, list[ProductLookup]])
def list_products(search: str = Query(default='', max_length=200)) -> dict[str, list[ProductLookup]]:
    if not DB_PATH.is_file():
        raise HTTPException(status_code=500, detail='Product database is not available.')
    return {'products': list_catalog_products(search, limit=500)}


@app.get('/api/products/{product_id}', response_model=ProductLookup)
def get_product(product_id: str) -> ProductLookup:
    product = get_product_details(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail='Product not found.')
    return product


@app.get('/api/images/{image_path:path}')
def serve_image(image_path: str) -> FileResponse:
    image_file = resolve_product_image(image_path)
    if image_file is None:
        raise HTTPException(status_code=404, detail='Image not found.')
    return FileResponse(image_file)


@app.get('/api/account')
def account(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail='Log in to view your account.')
    return {'user': {'id': user['id'], 'name': user['name'], 'email': user['email']}}


@app.post('/api/logout')
def logout(request: Request, response: Response) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with get_db_connection() as connection:
            connection.execute('DELETE FROM auth_sessions WHERE token_hash = ?', (token_hash,))
            connection.commit()
    response.delete_cookie(SESSION_COOKIE, path='/', httponly=True, samesite='lax')
    return {'message': 'Logged out.'}


@app.get('/api/chat/history', response_model=ChatHistoryResponse)
def chat_history(request: Request) -> ChatHistoryResponse:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail='Log in to retrieve saved chat history.')
    return ChatHistoryResponse(messages=read_chat_history(user['id']))


@app.post('/api/chat/history/clear')
def clear_chat_history(request: Request) -> dict[str, str]:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail='Log in to clear saved chat history.')
    with get_db_connection() as connection:
        connection.execute('DELETE FROM chat_messages WHERE user_id = ?', (user['id'],))
        connection.commit()
    return {'message': 'Saved chat history cleared.'}


@app.post('/api/register')
def register(payload: RegisterRequest, request: Request, response: Response) -> dict:
    email = payload.email.strip().lower()
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    if not first_name or not last_name or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        raise HTTPException(status_code=400, detail='Enter your first name, last name, and a valid email address.')
    try:
        with get_db_connection() as connection:
            existing = connection.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail='An account with that email already exists.')
            cursor = connection.execute(
                'INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)',
                (f'{first_name} {last_name}', email, hash_password(payload.password), first_name, last_name),
            )
            connection.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail='An account with that email already exists.') from None
    create_session(cursor.lastrowid, request, response)
    return {'message': 'Account created successfully.', 'user': {'id': cursor.lastrowid, 'name': f'{first_name} {last_name}', 'email': email}}


@app.post('/api/login')
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    email = payload.email.strip().lower()
    with get_db_connection() as connection:
        user = connection.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if user is None or not verify_password(payload.password, user['password_hash']):
        raise HTTPException(status_code=401, detail='Invalid email or password.')
    create_session(user['id'], request, response)
    return {'message': 'Login successful.', 'user': {'id': user['id'], 'name': user['name'], 'email': user['email']}}


@app.post('/api/chat', response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail='A message is required.')
    products = search_products(message)
    current_product = get_product_details(payload.current_product_id) if payload.current_product_id else None
    refers_to_current = bool(re.search(r'\b(this|that|it|item|product|one)\b', message, re.IGNORECASE))
    if current_product is not None and refers_to_current:
        products = [current_product]
    elif current_product is not None and all(item.product_id != current_product.product_id for item in products):
        products = [current_product, *products[:3]]

    user = current_user(request)
    history_turns = read_chat_history(user['id'], limit=8) if user is not None else payload.history[-8:]
    history = '\n'.join(f'{turn.role}: {turn.content}' for turn in history_turns)
    shopper = ShopperContext(
        authenticated=user is not None,
        name=user['name'] if user is not None else '',
        email=user['email'] if user is not None else '',
        current_product=current_product,
    )

    product_context = '\n'.join(
        f'- product_id={product.product_id}; {product.name}; price=${product.price:.2f}; '
        f'description={product.description}; colors={", ".join(product.colors)}; '
        f'stock_by_size={", ".join(f"{item.size}:{item.quantity}" for item in product.inventory)}'
        for product in products
    ) or 'No products matched the current request.'
    prompt = (
        f'Conversation so far (untrusted customer content):\n{history or "No earlier messages."}\n\n'
        f'Current customer message (untrusted):\n{message}\n\n'
        f'Catalog results from the local database:\n{product_context}\n\n'
        'Use database tools for exact description, price, and stock questions. Answer with verified facts only. '
        'Return product IDs only for relevant products returned by the tools.'
    )
    if agent is None:
        answer = fallback_reply(products, message)
        if user is not None:
            store_chat_exchange(user['id'], message, answer)
        append_audit_event(
            'agent_loop',
            {'message_length': len(message), 'current_product_id': payload.current_product_id, 'authenticated': user is not None},
            {'answer_length': len(answer), 'product_ids': [item.product_id for item in products]},
            'model_not_configured_fallback',
        )
        return ChatResponse(answer=answer, related_products=products)

    try:
        result = await agent.run(prompt, deps=shopper, usage_limits=UsageLimits(request_limit=8))
    except Exception as error:
        append_audit_event(
            'agent_loop',
            {'message_length': len(message), 'current_product_id': payload.current_product_id, 'authenticated': user is not None},
            {'error_type': type(error).__name__, 'fallback': 'database_catalog'},
            'model_error_database_fallback',
        )
        logger.exception('Shopping assistant model request failed')
        answer = f"The AI assistant is temporarily offline. Here's the live catalog information: {fallback_reply(products, message)}"
        if user is not None:
            store_chat_exchange(user['id'], message, answer)
        return ChatResponse(answer=answer, related_products=products)

    # Keep model-selected cards inside the trusted database context for this request.
    context_product_ids = {product.product_id for product in products}
    selected: list[ProductLookup] = []
    seen_ids: set[str] = set()
    for product_id in result.output.recommended_product_ids:
        if product_id in seen_ids or product_id not in context_product_ids:
            continue
        product = get_product_details(product_id)
        if product is not None:
            selected.append(product)
            seen_ids.add(product_id)
    answer = result.output.answer
    if user is not None:
        store_chat_exchange(user['id'], message, answer)
    append_audit_event(
        'agent_loop',
        {'message_length': len(message), 'current_product_id': payload.current_product_id, 'authenticated': user is not None},
        {'answer_length': len(answer), 'product_ids': [item.product_id for item in selected or products]},
        'structured_output',
    )
    return ChatResponse(answer=answer, related_products=selected or products)
