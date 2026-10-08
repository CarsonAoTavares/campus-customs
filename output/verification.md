# Homework 4 Verification

The final local verification used the project FastAPI service and the provided SQLite data pack.

- Frontend: `npm run build` and `npm run lint` passed.
- Backend: Python compilation passed.
- Catalog: 102 products loaded; Basic Hoodie Big Yale matched the database price of `$68.00` and 60 total units.
- Images: the catalog image endpoint returned a JPEG successfully.
- Authentication: the seeded account `test@campuscustoms.yale.edu` logged in successfully; a temporary new account registered, received a session, and was removed after verification.
- Password storage: the temporary account used `pbkdf2_sha256` with 600,000 iterations and did not store plaintext.
- Chat: hoodie recommendations returned four database-backed cards; the product-page price/stock question returned the exact `$68.00` price and per-size quantities.
- Persistence: signed-in chat history saved, reloaded, and cleared successfully; logout returned the account endpoint to 401.
- Model fallback: when the configured model request was unavailable, the API labeled the assistant offline and returned live catalog facts instead of inventing an answer.
- Grounding: model-selected recommendation IDs are intersected with the trusted products found for the current request before cards are returned.
