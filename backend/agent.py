from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

try:
    from .models import AgentReply, ShopperContext
    from .tools import get_product_details, get_product_stock, search_products
except ImportError:
    from models import AgentReply, ShopperContext
    from tools import get_product_details, get_product_stock, search_products

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = Path(__file__).resolve().parent / 'prompts' / 'prompt.md'
load_dotenv(BASE_DIR / '.env')
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding='utf-8')


def build_agent() -> Agent[ShopperContext, AgentReply] | None:
    portkey_key = os.getenv('PORTKEY_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    if portkey_key:
        provider = OpenAIProvider(api_key=portkey_key, base_url='https://ai.portkey.ai/v1')
    elif openai_key:
        provider = OpenAIProvider(api_key=openai_key)
    else:
        return None

    model_name = os.getenv('CAMPUS_CUSTOMS_MODEL', 'gpt-5')
    shopping_agent = Agent(
        OpenAIChatModel(model_name, provider=provider),
        output_type=AgentReply,
        deps_type=ShopperContext,
        system_prompt=SYSTEM_PROMPT,
        name='campus_customs_shopping_assistant',
        retries=1,
        tool_timeout=10,
    )
    shopping_agent.tool_plain(
        search_products,
        name='search_products',
        description='Search the local catalog by product name, type, description, color, or tag.',
    )
    shopping_agent.tool_plain(
        get_product_details,
        name='get_product_details',
        description='Look up a product by its catalog product ID for its exact description, price, colors, and image.',
    )
    shopping_agent.tool_plain(
        get_product_stock,
        name='get_product_stock',
        description='Look up exact inventory quantities by size for a catalog product ID.',
    )

    @shopping_agent.instructions
    def shopper_context_instructions(context: RunContext[ShopperContext]) -> str:
        shopper = context.deps
        lines = []
        if shopper.authenticated:
            lines.append(f"Authenticated shopper: {shopper.name}; account email: {shopper.email}.")
            lines.append('Use the shopper name naturally when helpful; keep account details private.')
        else:
            lines.append('The shopper is a guest; do not imply that you know their account identity.')
        if shopper.current_product is not None:
            lines.append(
                f"Current product page: {shopper.current_product.name} "
                f"(product_id={shopper.current_product.product_id}). "
                'Resolve this product through database tools before answering references such as "this item".'
            )
        else:
            lines.append('The shopper is not viewing a product detail page.')
        return ' '.join(lines)

    return shopping_agent


agent = build_agent()