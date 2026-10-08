from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InventoryLevel(BaseModel):
    size: str
    quantity: int
    in_stock: bool


class ProductLookup(BaseModel):
    product_id: str
    name: str
    garment_type: str
    description: str
    price: float
    image_url: str
    colors: list[str] = Field(default_factory=list)
    inventory: list[InventoryLevel] = Field(default_factory=list)
    total_inventory: int = 0
    available_sizes: list[str] = Field(default_factory=list)


class ProductStock(BaseModel):
    product_id: str
    name: str
    inventory: list[InventoryLevel] = Field(default_factory=list)
    total_inventory: int = 0
    available_sizes: list[str] = Field(default_factory=list)


class ChatTurn(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=2000)


class StoredChatMessage(ChatTurn):
    created_at: str


class ChatHistoryResponse(BaseModel):
    messages: list[StoredChatMessage] = Field(default_factory=list)


class ShopperContext(BaseModel):
    authenticated: bool = False
    name: str = ''
    email: str = ''
    current_product: ProductLookup | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    current_product_id: str | None = Field(default=None, max_length=150)


class AgentReply(BaseModel):
    answer: str
    recommended_product_ids: list[str] = Field(default_factory=list, max_length=4)


class ChatResponse(BaseModel):
    answer: str
    related_products: list[ProductLookup] = Field(default_factory=list, max_length=4)


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)