# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os
import re

from google.adk.tools.tool_context import ToolContext
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

PRODUCTS_DATA = {}

def load_data():
    global PRODUCTS_DATA
    PRODUCTS_DATA = {
        "smartphones": [{"category": "스마트폰"}],
        "pcs": [{"category": "PC"}],
        "tablets": [{"category": "태블릿"}],
        "wearables": [{"category": "웨어러블"}],
        "tvs_monitors": [{"category": "TV"}],
        "home_appliances": [{"category": "생활가전"}]
    }

load_data()

def _extract_json(text: str) -> str:
    # Extract JSON array or object from markdown code blocks
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    
    start_arr = text.find('[')
    end_arr = text.rfind(']')
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        return text[start_arr:end_arr+1].strip()
    
    start_obj = text.find('{')
    end_obj = text.rfind('}')
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        return text[start_obj:end_obj+1].strip()
    return text.strip()

def get_categories(tool_context: ToolContext) -> str:
    """Returns a list of unique product categories with image URLs."""
    logger.info("--- TOOL CALLED: get_categories ---")
    
    # Mapping from category ID to public image URL
    image_mapping = {
        "smartphones": "https://newsimg.koreatimes.co.kr/2026/04/15/1a4137eb-3cad-4765-a899-b0e9c03794c8.jpg",
        "pcs": "https://images.samsung.com/is/image/samsung/p6pim/uk/feature/others/uk-feature-galaxy-book6-ultra-16-inch-np960ujhe-583471-551446472?448_n_JPG",
        "tablets": "https://image-us.samsung.com/SamsungUS/pim/migration/mobile/tablets/all-other-tablets/sm-t550nzwaxar/Pdpkeyfeature-sm-t550nzwaxar-600x600-C1-062016.jpg?product-details-jpg",
        "wearables": "https://images.samsung.com/is/image/samsung/p6pim/au/f2507/gallery/au-galaxy-watch8-l330-sm-l330nzsaxsa-thumb-547637123",
        "tvs_monitors": "https://images.samsung.com/is/image/samsung/p6pim/uk/qe77s99hatxxu/gallery/uk-oled-s95h-qe77s99hatxxu-551788607?200_200_PNG",
        "home_appliances": "https://images.samsung.com/is/image/samsung/assets/latin_en/sustainability/accessibility/home-appliances/sustainability_accessibility_homeappliances_general_mo_720x540.jpg?720_N_JPG"
    }
    
    result = []
    for key, products in PRODUCTS_DATA.items():
        if products:
            korean_cat = products[0].get("category", key)
            img_url = image_mapping.get(key, "https://picsum.photos/100/100?random=" + key)
            
            result.append({
                "id": key, 
                "category": korean_cat,
                "imageUrl": img_url
            })
            
    return json.dumps(result, ensure_ascii=False)

async def search_latest_products(category_name: str, tool_context: ToolContext, exclude_product: str = None) -> str:
    """Searches the web for the latest 3-4 products in the given category (e.g., '스마트폰', '태블릿') and returns them as a JSON list. Option to exclude one product."""
    logger.info(f"--- TOOL CALLED: search_latest_products (Category Name: {category_name}, Exclude: {exclude_product}) ---")
    
    cat_map = {
        "스마트폰": "smartphones",
        "PC": "pcs",
        "태블릿": "tablets",
        "웨어러블": "wearables",
        "TV": "tvs_monitors",
        "생활가전": "home_appliances"
    }
    category_id = cat_map.get(category_name, "smartphones")
    setattr(tool_context, "current_category", category_id)
    logger.info(f"Updated current_category in tool_context: {category_id}")
    
    client = genai.Client()
    prompt = f"""
    Search the web for the latest and most popular products in the category '{category_name}'.
    Find exactly 3-4 current models that are actively sold in 2025/2026.
    {f"Do NOT include the product '{exclude_product}' in the results." if exclude_product else ""}
    
    For each product, collect:
    1. The exact product name (e.g., 'Galaxy S25 Ultra').
    2. A short spec summary (e.g., 'Snapdragon 8 Elite, 6.9 inch Dynamic AMOLED, 200MP').
    3. The approximate price in Korean Won (KRW) (e.g., '1,698,000 KRW').
    4. The official product page URL. **CRITICAL**: Only include this if you find a real, active, official URL. If you cannot find a verified official URL, set "url" to null. Do NOT hallucinate or guess URLs.
    
    You MUST respond with a valid JSON array of objects. Do NOT wrap it in markdown blocks. Just the raw JSON.
    Each object MUST have the following keys:
    - "name": Exact product name.
    - "category": "{category_name}"
    - "url": Product detail/homepage URL (MUST be a real, verified URL, or null if not found).
    - "release_date": Release date (YYYY-MM-DD), approximate if not exact.
    - "spec": The spec summary.
    - "price": The price string.
    - "imageUrl": A placeholder image URL, e.g., "https://picsum.photos/100/100?random=<unique_number>"
    """
    
    try:
        response = client.models.generate_content(
            model=os.environ.get("MODEL", "gemini-3.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        result_text = _extract_json(response.text or "[]")
        logger.info(f"Dynamic products result: {result_text}")
        return result_text
    except Exception as e:
        logger.error(f"Error during search_latest_products: {e}")
        return "[]"

async def compare_products(product_names_str: str, tool_context: ToolContext) -> str:
    """Compares specifications of given products by searching the web. Provide product names separated by comma."""
    logger.info(f"--- TOOL CALLED: compare_products (Products: {product_names_str}) ---")
    names = [n.strip() for n in product_names_str.split(",")]
    
    client = genai.Client()
    prompt = f"""
    For each product, you MUST find:
    1. The category.
    2. The exact product name.
    3. The official product page URL. **CRITICAL**: Only include this if you find a real, active, official URL. If you cannot find a verified official URL, set "product_url" to null. Do NOT hallucinate or guess URLs.
    4. Detailed specs (processor, display, camera, battery, memory_storage, price).
    
    You MUST respond with a single JSON object where keys are the product names, and values are objects containing their detailed specs.
    Example:
    {{
      "Product A": {{
        "category": "스마트폰",
        "product_name": "Product A",
        "product_url": "https://www.example.com/products/product-a/",
        "specs": {{
          "processor": "Octa-core Processor",
          "display": "6.7 inch AMOLED",
          "camera": "50MP Main",
          "battery": "5,000mAh",
          "memory_storage": "12GB RAM",
          "price": "1,000,000 KRW"
        }}
      }}
    }}
    """
    try:
        response = client.models.generate_content(
            model=os.environ.get("MODEL", "gemini-3.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        result_text = _extract_json(response.text or "{{}}")
        logger.info(f"Dynamic comparison result: {result_text}")
        return result_text
    except Exception as e:
        logger.error(f"Error during compare_products: {e}")
        return "{{}}"

def save_selection(product_names: str, tool_context: ToolContext, session_id: str = None) -> str:
    """Saves selected products to session state for long-term memory. Provide product names separated by comma."""
    logger.info(f"--- TOOL CALLED: save_selection (Products: {product_names}) ---")
    names = [n.strip() for n in product_names.split(",")]
    setattr(tool_context, "selected_products", names)
    logger.info(f"Updated selected_products in tool_context: {names}")
    return json.dumps({"success": True, "saved": names}, ensure_ascii=False)

def get_selected_products(tool_context: ToolContext, session_id: str = None) -> str:
    """Returns the list of selected products for the current session."""
    selected_products = getattr(tool_context, "selected_products", [])
    return json.dumps(selected_products, ensure_ascii=False)