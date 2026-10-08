# Data Harness

This file captures the schema and business meaning of the local Campus Customs data so the storefront and chatbot can stay grounded in the real database.

## Table: catalogue

Fields:

- product_id — Unique identifier for each item; used to join the catalog to inventory and to reference products in the chatbot and storefront.
- name — Human-readable product name shown in the shopping UI and used by the assistant for matching search queries.
- garment_type — Product category such as hoodie, crewneck, or T-shirt; helps the chatbot group recommendations by type and supports browsing.
- description — Product details and marketing copy; useful for the assistant to explain product value and for customers to understand what they are buying.
- colors — Available color options for the item; useful for filtering recommendations and matching customer preferences.
- search_tags — Keywords used for semantic matching in product search and chat recommendations.
- image_file_path — Relative path to the product image asset; the storefront uses this to render product photos and the backend serves these files.
- price — Current price of the product in dollars; this is critical for accurate assistant answers and price display.

## Table: inventory

Fields:

- id — Internal row ID for the stock record; helps uniquely identify each inventory row.
- product_id — Links each size record to the correct product in the catalogue table.
- size — The stock size label for a product, such as XS, S, M, L, or XL; necessary for size-specific availability and recommendations.
- quantity — Number of units available for that product size; this is the key fact for availability checks and stock accuracy.

## Table: users

Fields:

- id — Unique user row identifier; used for account records and database lookups.
- name — Full display name stored for the user profile and storefront account display.
- email — User login and account identity; used for registration validation and authentication.
- password_hash — Salted PBKDF2-HMAC-SHA256 password verifier; lets the backend check login credentials without storing the password itself.
- created_at — Timestamp for when the account was created; useful for user history and auditing.
- first_name — Customer first name; helps personalize registration and account display.
- last_name — Customer last name; helps personalize registration and account display.

## Account authentication

- Registration posts first name, last name, email, and password to `/api/register`. The backend trims and lowercases the email, checks for an existing account, then stores the full name, email, and password hash in `users`. The confirm-password field is checked in the frontend and is never sent to or stored by the backend.
- New passwords must be 12–128 characters. Each password is hashed with PBKDF2-HMAC-SHA256 using 600,000 iterations and a fresh cryptographically random salt. The stored format is `pbkdf2_sha256$600000$<salt>$<digest>`; the plaintext password is never stored.
- The supplied seed account uses the older three-part `pbkdf2_sha256$<salt>$<digest>` format. Login verifies those legacy records using the original 120,000 iterations, while new registrations use the stronger versioned format.
- Login posts email and password to `/api/login`. The backend derives a verifier using the stored salt and iteration count, compares it with `hmac.compare_digest`, and returns the same invalid-credentials response for an unknown email or incorrect password.
- Login and registration issue a 30-day opaque HttpOnly cookie. Only a SHA-256 hash of its token is stored in `auth_sessions`; the raw token is not stored in SQLite.
- Authenticated user and assistant messages are stored in `chat_messages` with `user_id`, `role`, `content`, and `created_at`. `/api/chat/history` reloads up to 100 messages; the agent receives the latest 8 as conversational context. Guests may chat, but their history is held only in the browser and is not saved to SQLite.

## Pydantic models and field choices

- `InventoryLevel`: `size` and exact `quantity` come from the `inventory` table; `in_stock` makes zero-quantity sizes explicit rather than leaving the agent or UI to infer availability.
- `ProductLookup`: `product_id` is the stable detail-page and inventory join key; `name`, `garment_type`, `description`, `price`, `colors`, and `image_url` support answers and cards; `inventory`, `total_inventory`, and `available_sizes` support size-specific and aggregate stock questions.
- `ProductStock`: `product_id` and `name` identify the item; `inventory` carries each size/quantity/availability row; `total_inventory` and `available_sizes` are convenient computed summaries.
- `ChatTurn`: `role` distinguishes customer and assistant text; `content` holds one turn and is limited to 2,000 characters.
- `StoredChatMessage`: adds `created_at` to a chat turn so saved history can be ordered and displayed after reload.
- `ChatHistoryResponse`: `messages` is the ordered history payload returned to the logged-in shopper.
- `ShopperContext`: `authenticated` gates personalization; `name` and `email` identify the account to the agent; `current_product` carries the canonical database-backed product for references such as “this”.
- `ChatRequest`: `message` is the current question; `history` supports guest conversation context (up to 12 turns); `current_product_id` identifies the visible product and is resolved against SQLite rather than trusted as product data.
- `AgentReply`: `answer` is customer-facing text; `recommended_product_ids` is a maximum-four ID list that lets the API resolve every card back to the database.
- `ChatResponse`: `answer` and `related_products` define the frontend chat contract; each related product has the same fields as catalog cards.
- `RegisterRequest` and `LoginRequest`: typed names, email, and password are validated at the API boundary; registration passwords are 12–128 characters and login never returns password data.

## Agent tools

- `search_products(query, limit=4)` searches names, garment types, descriptions, colors, and tags; it filters common question filler and ranks name/type matches ahead of incidental description matches. Its hard cap is 12 results.
- `get_product_details(product_id)` returns the canonical database-backed description, price, colors, and image URL for an exact ID.
- `get_product_stock(product_id)` returns exact quantity and `in_stock` status for every size, including zero-stock sizes.
- Product cards are returned in `ChatResponse.related_products` with a maximum of four. The frontend uses each `product_id` in the same hash detail route used by catalog cards.
- The API also intersects model-returned recommendation IDs with the current database search/context results before resolving cards, so a model cannot introduce an unrelated catalog item through a fabricated or stale ID.

## Chat and agent flow

1. The React client calls `/api/chat` with `message`, up to 8 recent guest turns, and optional `current_product_id`.
2. FastAPI resolves the current product ID from SQLite. For authenticated users it loads history from `chat_messages` and identifies the shopper from the HttpOnly session; client-supplied history is not used for signed-in accounts.
3. `backend/agent.py` loads `backend/prompts/prompt.md` at startup, configures PydanticAI with `CAMPUS_CUSTOMS_MODEL` (default `gpt-5`), and uses Portkey when `PORTKEY_API_KEY` is configured, otherwise the OpenAI provider when `OPENAI_API_KEY` is configured.
4. The agent receives a typed `ShopperContext`, can call the three database tools, and returns `AgentReply`. FastAPI resolves recommended IDs back to `ProductLookup` objects before returning structured cards.
5. Successful authenticated exchanges are appended to `chat_messages`; guest turns remain client-side. If no model key is configured, or a model request fails, the API returns a database-backed fallback and labels model failures as offline instead of inventing an AI response.
- Structured recommendations appear both in the assistant transcript and in a page-level “Matches for…” band. Both use the same product-card component and `#product/{product_id}` route as the catalog.

## Runtime limits and audit

- PydanticAI request/agent loop: at most 8 model requests per chat run; output/tool validation retries: 1; tool timeout: 10 seconds.
- Chat API input: message 1–2,000 characters; history at most 12 turns at validation, with the latest 8 supplied to the agent. Persisted-history response cap: 100 messages.
- Search tool: default 4 results, hard maximum 12. Structured recommendations and chat response cards: maximum 4. Catalog endpoint: maximum 500 products.
- `output/audit_trail.json` is a JSON array retained across runs. Each tool event records UTC time, tool name, short arguments/results, and an empty stop reason; each completed/fallback/error agent loop records its stop reason. Email-like values and credential-shaped strings are redacted.
- The audit log does not include raw session tokens, passwords, or the shopper email from agent dependencies.

## API routes and local commands

- `GET /api/health`, `GET /api/products`, `GET /api/products/{product_id}`, and `GET /api/images/{image_path}` serve status, catalog, details, and local product images.
- `POST /api/register`, `POST /api/login`, `GET /api/account`, and `POST /api/logout` provide account/session behavior.
- `POST /api/chat`, `GET /api/chat/history`, and `POST /api/chat/history/clear` provide chat, saved history, and history clearing.
- Run the backend from the `backend/` directory with the project virtualenv active: `uvicorn main:app --reload --port 8000`.
- Run the frontend from `frontend/` with `npm run dev`. Vite proxies `/api` to `http://127.0.0.1:8000` so browser requests and session cookies stay same-origin.
- Set `PORTKEY_API_KEY` or `OPENAI_API_KEY` in the workspace `.env`; never commit the key. `CAMPUS_CUSTOMS_MODEL` can override the default model name.

## Notes for the shop and the chatbot

- The catalogue and inventory tables together make up the product truth source for pricing, stock, and merchandising.
- The users table is the source of truth for account registration and login behavior.
- The assistant must use these tables rather than assumptions or vendor metadata when giving product recommendations.
