
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

from google.adk.tools.tool_context import ToolContext
from state_manager import GLOBAL_SESSIONS

logger = logging.getLogger(__name__)

PRODUCTS_DATA = {}

def load_data():
    global PRODUCTS_DATA
    try:
        script_dir = os.path.dirname(__file__)
        json_path = os.path.join(script_dir, "sample_samsung.json")
        with open(json_path, mode="r", encoding="utf-8") as file:
            PRODUCTS_DATA = json.load(file)
        logger.info(f"Successfully loaded products data from JSON.")
    except Exception as e:
        logger.error(f"Error loading JSON: {e}")

load_data()

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

def get_products_by_category(category_id: str, tool_context: ToolContext, exclude_product: str = None) -> str:
    """Returns a list of products in a given category ID (e.g., 'smartphones'). Option to exclude one product."""
    from state_manager import session_context
    session_id = getattr(session_context, "id", None)
    
    logger.info(f"--- TOOL CALLED: get_products_by_category (Category ID: {category_id}, Exclude: {exclude_product}) ---")
    
    if session_id:
        if session_id not in GLOBAL_SESSIONS:
            GLOBAL_SESSIONS[session_id] = {}
        GLOBAL_SESSIONS[session_id]["current_category"] = category_id
        logger.info(f"Updated current_category in GLOBAL_SESSIONS for {session_id}: {category_id}")
        
    products = PRODUCTS_DATA.get(category_id, [])
    
    result = []
    for p in products:
        if exclude_product and p.get("product_name") == exclude_product:
            continue
        result.append({
            "name": p.get("product_name"),
            "category": p.get("category"),
            "url": p.get("product_url"),
            "release_date": p.get("release_date"),
            "spec": str(p.get("specs", {})).replace("{", "").replace("}", ""),
            "price": p.get("specs", {}).get("price", ""),
            "imageUrl": "https://picsum.photos/100/100?random=" + str(hash(p.get("product_name")) % 100)
        })
    return json.dumps(result, ensure_ascii=False)

def get_product_details(product_name: str, tool_context: ToolContext) -> str:
    """Returns details of a specific product."""
    logger.info(f"--- TOOL CALLED: get_product_details (Product: {product_name}) ---")
    for cat, products in PRODUCTS_DATA.items():
        for p in products:
            if p.get("product_name") == product_name:
                return json.dumps(p, ensure_ascii=False)
    return json.dumps({"error": "Product not found"}, ensure_ascii=False)

def compare_products(product_names_str: str, tool_context: ToolContext) -> str:
    """Compares specifications of given products. Provide product names separated by comma."""
    logger.info(f"--- TOOL CALLED: compare_products (Products: {product_names_str}) ---")
    names = [n.strip() for n in product_names_str.split(",")]
    result = {}
    for name in names:
        for cat, products in PRODUCTS_DATA.items():
            for p in products:
                if p.get("product_name") == name:
                    result[name] = p
    return json.dumps(result, ensure_ascii=False)

def save_selection(product_names: str, tool_context: ToolContext, session_id: str = None) -> str:
    """Saves selected products to session state for long-term memory. Provide product names separated by comma."""
    if not session_id:
        from state_manager import session_context
        session_id = getattr(session_context, "id", None)
    
    logger.info(f"--- TOOL CALLED: save_selection (Session: {session_id}, Products: {product_names}) ---")
    
    if not session_id:
        logger.error("No session_id found in context!")
        return json.dumps({"success": False, "error": "No session_id"}, ensure_ascii=False)
        
    names = [n.strip() for n in product_names.split(",")]
    
    if session_id not in GLOBAL_SESSIONS:
        GLOBAL_SESSIONS[session_id] = {}
        
    GLOBAL_SESSIONS[session_id]["selected_products"] = names
    logger.info(f"Updated state in GLOBAL_SESSIONS for {session_id}: {GLOBAL_SESSIONS[session_id]}")
    
    return json.dumps({"success": True, "saved": names}, ensure_ascii=False)

def get_selected_products(tool_context: ToolContext, session_id: str = None) -> str:
    """Returns the list of selected products for the current session."""
    if not session_id:
        from state_manager import session_context
        session_id = getattr(session_context, "id", None)
    
    if not session_id:
        return json.dumps([], ensure_ascii=False)
        
    state = GLOBAL_SESSIONS.get(session_id, {})
    return json.dumps(state.get("selected_products", []), ensure_ascii=False)
