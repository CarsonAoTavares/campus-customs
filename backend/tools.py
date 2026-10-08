from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

try:
    from .audit import append_audit_event
    from .models import InventoryLevel, ProductLookup, ProductStock
except ImportError:
    from audit import append_audit_event
    from models import InventoryLevel, ProductLookup, ProductStock

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'campus_customs.db'
PRODUCTS_DIR = DATA_DIR / 'products'


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def _colors(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _inventory(product_id: str) -> list[InventoryLevel]:
    with get_db_connection() as connection:
        rows = connection.execute(
            'SELECT size, quantity FROM inventory WHERE product_id = ? ORDER BY size',
            (product_id,),
        ).fetchall()
    return [
        InventoryLevel(size=row['size'], quantity=int(row['quantity']), in_stock=int(row['quantity']) > 0)
        for row in rows
    ]


def _product_from_row(row: sqlite3.Row) -> ProductLookup:
    inventory = _inventory(row['product_id'])
    image_path = str(row['image_file_path'] or '').lstrip('/')
    return ProductLookup(
        product_id=row['product_id'],
        name=row['name'],
        garment_type=row['garment_type'] or '',
        description=row['description'] or '',
        price=float(row['price']),
        image_url=f'/api/images/{image_path}',
        colors=_colors(row['colors']),
        inventory=inventory,
        total_inventory=sum(item.quantity for item in inventory),
        available_sizes=[item.size for item in inventory if item.in_stock],
    )


def list_catalog_products(search: str = '', limit: int = 500) -> list[ProductLookup]:
    if not DB_PATH.is_file():
        return []
    with get_db_connection() as connection:
        rows = connection.execute('SELECT * FROM catalogue ORDER BY name').fetchall()

    term = search.strip().lower()
    tokens = [token for token in re.sub(r'[^a-z0-9\s]', ' ', term).split() if token]
    results: list[ProductLookup] = []
    for row in rows:
        searchable = ' '.join((
            row['name'] or '', row['garment_type'] or '', row['description'] or '',
            row['colors'] or '', row['search_tags'] or '',
        )).lower()
        if tokens and not any(token in searchable for token in tokens):
            continue
        results.append(_product_from_row(row))
        if len(results) >= limit:
            break
    return results


def search_products(query: str, limit: int = 4) -> list[ProductLookup]:
    """Find catalog products by name, garment type, description, color, or search tag."""
    stop_words = {'a', 'an', 'are', 'available', 'can', 'do', 'for', 'have', 'i', 'in', 'is', 'me', 'of', 'on', 'please', 'show', 'some', 'the', 'this', 'to', 'what', 'with', 'you'}
    raw_tokens = re.sub(r'[^a-z0-9\s]', ' ', query.lower()).split()
    tokens = [token[:-1] if token.endswith('s') and len(token) > 4 else token for token in raw_tokens if token not in stop_words]
    if not tokens:
        matches: list[ProductLookup] = []
    else:
        scored: list[tuple[int, ProductLookup]] = []
        for product in list_catalog_products(limit=500):
            name = product.name.lower()
            garment_type = product.garment_type.lower()
            description = product.description.lower()
            tags_and_colors = ' '.join((*product.colors, product.garment_type)).lower()
            score = 0
            for token in tokens:
                if token in name:
                    score += 6 if name.startswith(token) else 4
                if token in garment_type:
                    score += 5
                if token in tags_and_colors:
                    score += 2
                if token in description:
                    score += 1
            if score:
                scored.append((score, product))
        scored.sort(key=lambda item: (-item[0], item[1].name.lower()))
        matches = [product for _, product in scored[:max(1, min(limit, 12))]]
    append_audit_event(
        'search_products', {'query': query[:100], 'limit': limit},
        {'match_count': len(matches), 'product_ids': [item.product_id for item in matches]},
    )
    return matches


def get_product_details(product_id: str) -> ProductLookup | None:
    """Return the database description, price, colors, and image URL for one product ID."""
    with get_db_connection() as connection:
        row = connection.execute('SELECT * FROM catalogue WHERE product_id = ?', (product_id,)).fetchone()
    product = _product_from_row(row) if row else None
    append_audit_event(
        'get_product_details', {'product_id': product_id[:100]},
        {'found': product is not None, 'name': product.name if product else None, 'price': product.price if product else None},
    )
    return product


def get_product_stock(product_id: str) -> ProductStock | None:
    """Return exact inventory quantities by size for one product ID."""
    with get_db_connection() as connection:
        row = connection.execute(
            'SELECT product_id, name FROM catalogue WHERE product_id = ?', (product_id,)
        ).fetchone()
    if row is None:
        append_audit_event('get_product_stock', {'product_id': product_id[:100]}, {'found': False})
        return None
    inventory = _inventory(product_id)
    stock = ProductStock(
        product_id=product_id,
        name=row['name'],
        inventory=inventory,
        total_inventory=sum(item.quantity for item in inventory),
        available_sizes=[item.size for item in inventory if item.in_stock],
    )
    append_audit_event(
        'get_product_stock', {'product_id': product_id[:100]},
        {'product_name': stock.name, 'stock_by_size': [{'size': item.size, 'quantity': item.quantity} for item in stock.inventory]},
    )
    return stock


def resolve_product_image(image_path: str) -> Path | None:
    candidate = (DATA_DIR / image_path).resolve()
    products_root = PRODUCTS_DIR.resolve()
    if not candidate.is_relative_to(products_root) or not candidate.is_file():
        return None
    return candidate