# Campus Customs Usability Improvements

## Frontend Improvements

### 1. Search and category filtering

**What I added:** The Products section will include a live text search and garment-type filter over the database-backed catalog.

**Benefit:** Shoppers can narrow a large merchandise collection to relevant items without paging through unrelated products, while the catalog remains grounded in the shop's real inventory.

### 2. Guided, manageable chat

**What I added:** The floating chat will offer one-tap example questions, show a clear loading state, render matching products as clickable cards, and provide a control to clear the visible conversation.

**Benefit:** Customers can discover what to ask, understand when a reply is being prepared, open a recommendation's full detail page, and reset the chat without reloading the storefront.

## Agent and Backend Improvements

### 3. Ranked database search

**What I added:** Catalog search will normalize common question filler and plural forms, prioritize product-name and garment-type matches, and use descriptions and tags as secondary signals. Results retain typed price, description, image, and size-stock data from SQLite.

**Benefit:** Questions such as “What hoodies are available?” return hoodie products ahead of incidental text matches, and answers can cite exact per-size quantities, including zero-stock sizes.

### 4. Page-aware, stock-grounded answers

**What I added:** Chat requests include the currently viewed product ID. The backend resolves that ID against SQLite and passes the canonical product and logged-in shopper identity to the agent as typed dependencies; stock questions can call the per-size inventory tool.

**Benefit:** Follow-ups such as “Is this available in pink?” have a reliable product referent, and the assistant does not need to guess which listing the customer means.

## Core Chat Memory

Logged-in shoppers receive an opaque HttpOnly session cookie. Their user and assistant turns are stored in the SQLite `chat_messages` table and reloaded through the authenticated history endpoint when they return. Guest conversations remain in the current browser session and are not written to the database.