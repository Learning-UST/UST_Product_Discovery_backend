import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import boto3
from dotenv import load_dotenv
from opensearchpy import helpers
from pymongo import MongoClient

from services.opensearch_service import OpenSearchService


def _as_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_date_yyyy_mm_dd(value: str):
    text = _as_str(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None


def _is_active_promo(promo: dict) -> bool:
    if not promo.get("isPromotion", False):
        return False
    today = datetime.now(timezone.utc).date()
    start = _parse_date_yyyy_mm_dd(promo.get("Start_Date"))
    end = _parse_date_yyyy_mm_dd(promo.get("End_Date"))
    if start and end:
        return start <= today <= end
    return True


def _normalize_upc(value) -> str:
    text = _as_str(value)
    if not text:
        return ""
    if text.upper().startswith("SKU_") or text.upper().startswith("INV_"):
        text = text.split("_", 1)[1]
    return text


def _extract_product_id(product: dict):
    return (
        product.get("product_id")
        or product.get("Product_Id")
        or product.get("productId")
    )


def _extract_name(product: dict):
    return product.get("name") or product.get("Name")


def _extract_brand(product: dict):
    return product.get("brand") or product.get("Brand")


def _extract_category(product: dict):
    return product.get("category") or product.get("Category")


def _extract_description(product: dict):
    return product.get("description") or product.get("Description")


def _find_best_promo(product: dict, promos: List[dict]) -> Optional[dict]:
    product_id = _as_str(_extract_product_id(product))
    brand = _extract_brand(product)
    category = _extract_category(product)
    applicable = []

    for promo in promos:
        if not _is_active_promo(promo):
            continue
        scope_type = promo.get("Scope_Type")
        scope_value = promo.get("Scope_Value")
        if scope_type == "Brand" and brand == scope_value:
            applicable.append(promo)
        elif scope_type == "Category" and category == scope_value:
            applicable.append(promo)
        elif scope_type == "Product" and product_id and product_id == _as_str(scope_value):
            applicable.append(promo)

    if not applicable:
        return None

    applicable.sort(key=lambda x: x.get("Priority", 999))
    return applicable[0]


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _as_str(value).replace(",", "").replace("$", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _to_int(value, default=0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _safe_id(product: dict, upc: str, idx: int) -> str:
    provided = product.get("id")
    if _as_str(provided):
        return _as_str(provided)

    product_id = _extract_product_id(product)
    if _as_str(product_id):
        return f"P_{product_id}"
    if upc:
        return f"SKU_{upc}"
    return f"AUTO_{idx}"


def _build_embedding_text(doc: dict) -> str:
    parts = [
        f"Name: {_as_str(doc.get('name'))}",
        f"Brand: {_as_str(doc.get('brand'))}",
        f"Category: {_as_str(doc.get('category'))}",
        f"Description: {_as_str(doc.get('description'))}",
        f"Ingredients: {_as_str(doc.get('ingredients'))}",
        f"Nutrition: {_as_str(doc.get('nutrition'))}",
        f"Country of origin: {_as_str(doc.get('country_of_origin'))}",
        f"Shelf life: {_as_str(doc.get('shelf_life'))}",
    ]
    return ". ".join([p for p in parts if _as_str(p)])


def _normalize_combined_doc(item: dict, idx: int) -> dict:
    metadata = item.get("metadata") or {}
    promotion = item.get("promotion") or {}

    doc = {
        "id": _safe_id(item, _normalize_upc(item.get("upc") or item.get("UPC")), idx),
        "product_id": item.get("product_id") or item.get("Product_Id"),
        "name": item.get("name") or item.get("Name"),
        "brand": item.get("brand") or item.get("Brand"),
        "category": item.get("category") or item.get("Category"),
        "description": item.get("description") or item.get("Description"),
        "price": _to_float(item.get("price") or item.get("Price")),
        "discounted_price": _to_float(item.get("discounted_price") or item.get("Discounted_Price")),
        "stock": _to_int(item.get("stock") or item.get("Quantity"), 0),
        "store_id": item.get("store_id"),
        "image_url": item.get("image_url"),
        "country_of_origin": item.get("country_of_origin") or item.get("Country_Of_Origin"),
        "veg": bool(metadata.get("veg") if metadata.get("veg") is not None else item.get("Veg", False)),
        "age_restricted": bool(metadata.get("age_restricted", item.get("age_restricted", False))),
        "ingredients": metadata.get("ingredients") or item.get("Ingredients") or [],
        "nutrition": metadata.get("nutrition") or item.get("Nutritional_Facts") or {},
        "upc": _normalize_upc(item.get("upc") or item.get("UPC")),
        "promotion_name": promotion.get("name") or item.get("Promotion_Name"),
    }

    if metadata.get("nutrition") is not None and not isinstance(doc["nutrition"], str):
        doc["nutrition"] = json.dumps(doc["nutrition"], ensure_ascii=True)

    doc["embedding_text"] = _build_embedding_text(doc)
    return doc


def _load_docs_from_json(json_path: Path) -> List[dict]:
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError("JSON input must be a list of product documents")

    docs = []
    for idx, item in enumerate(raw):
        if isinstance(item, dict):
            docs.append(_normalize_combined_doc(item, idx))
    return docs


def _mongo_collection_name(key: str, default: str) -> str:
    value = os.getenv(key)
    if value and value.strip():
        return value.strip()
    return default


def _load_docs_from_mongo() -> List[dict]:
    mongo_uri = _as_str(os.getenv("AWS_MONGODB_URI"))
    db_name = _as_str(os.getenv("AWS_MONGODB_DB_NAME"))
    if not mongo_uri or not db_name:
        raise ValueError("AWS_MONGODB_URI and AWS_MONGODB_DB_NAME are required")

    products_col = _mongo_collection_name("AWS_MONGODB_PRODUCTS_COLLECTION", "products")
    inventory_col = _mongo_collection_name("AWS_MONGODB_INVENTORY_COLLECTION", "inventory")
    promotion_col = _mongo_collection_name("AWS_MONGODB_PROMOTION_COLLECTION", "promotion")

    client = MongoClient(mongo_uri)
    db = client[db_name]

    try:
        products = list(db[products_col].find({}, {"_id": 0}))
        inventory = list(db[inventory_col].find({}, {"_id": 0}))
        promos = list(db[promotion_col].find({}, {"_id": 0}))
    finally:
        client.close()

    inv_map: Dict[str, dict] = {}
    for inv in inventory:
        upc = _normalize_upc(inv.get("upc") or inv.get("UPC") or inv.get("id"))
        if upc:
            inv_map[upc] = inv

    docs = []
    for idx, product in enumerate(products):
        upc = _normalize_upc(product.get("upc") or product.get("UPC") or product.get("id"))
        inv = inv_map.get(upc, {})
        promo = _find_best_promo(product, promos)

        base_price = _to_float(inv.get("Price") or inv.get("price") or product.get("Price") or product.get("price"))
        discounted_price = base_price
        if promo and base_price is not None:
            pct = _to_float(promo.get("Discount_Percentage")) or 0.0
            discounted_price = round(base_price * (1.0 - (pct / 100.0)), 2)

        nutrition = product.get("Nutritional_Facts") or product.get("nutrition") or {}
        if not isinstance(nutrition, str):
            nutrition = json.dumps(nutrition, ensure_ascii=True)

        doc = {
            "id": _safe_id(product, upc, idx),
            "product_id": _extract_product_id(product),
            "name": _extract_name(product),
            "brand": _extract_brand(product),
            "category": _extract_category(product),
            "description": _extract_description(product),
            "price": base_price,
            "discounted_price": discounted_price,
            "stock": _to_int(inv.get("Quantity") or inv.get("quantity"), 0),
            "store_id": inv.get("store_id"),
            "image_url": product.get("image_url"),
            "country_of_origin": product.get("Country_Of_Origin") or product.get("country_of_origin"),
            "veg": bool(product.get("Veg") if product.get("Veg") is not None else product.get("veg", False)),
            "age_restricted": bool(product.get("age_restricted", False)),
            "ingredients": product.get("Ingredients") or product.get("ingredients") or [],
            "nutrition": nutrition,
            "upc": upc,
            "promotion_name": promo.get("Promotion_Name") if promo else None,
        }
        doc["embedding_text"] = _build_embedding_text(doc)
        docs.append(doc)

    return docs


def _chunked(items: List[dict], size: int) -> Iterable[List[dict]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _bedrock_client(region: str):
    kwargs = {"region_name": region}
    access_key = _as_str(os.getenv("AWS_ACCESS_KEY_ID"))
    secret_key = _as_str(os.getenv("AWS_SECRET_ACCESS_KEY"))
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
    return boto3.client("bedrock-runtime", **kwargs)


def _embed_one(client, model_id: str, text: str) -> List[float]:
    payload = {"inputText": text}
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload),
    )
    body = json.loads(response["body"].read())
    embedding = body.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise ValueError("Bedrock embedding response did not include a valid vector")
    return embedding


def _apply_embeddings(docs: List[dict], region: str, model_id: str) -> int:
    client = _bedrock_client(region)
    dimension = 0
    for idx, doc in enumerate(docs, start=1):
        text = _as_str(doc.get("embedding_text"))
        if not text:
            text = _build_embedding_text(doc)
        vector = _embed_one(client, model_id, text)
        doc["embedding"] = vector
        if dimension == 0:
            dimension = len(vector)
        if idx % 100 == 0:
            print(f"Embedded {idx}/{len(docs)}")
    return dimension


def _index_exists(client, index_name: str) -> bool:
    return bool(client.indices.exists(index=index_name))


def _create_index(client, index_name: str, vector_dimension: int):
    schema = OpenSearchService.get_index_schema()
    schema["mappings"]["properties"]["embedding"]["dimension"] = vector_dimension
    client.indices.create(index=index_name, body=schema)


def _delete_index_if_exists(client, index_name: str):
    if _index_exists(client, index_name):
        client.indices.delete(index=index_name)


def _bulk_insert(client, index_name: str, docs: List[dict], batch_size: int):
    total_success = 0
    total_failed = 0

    for batch_index, batch in enumerate(_chunked(docs, batch_size), start=1):
        actions = [
            {
                "_index": index_name,
                "_id": _as_str(doc.get("id")),
                "_source": doc,
            }
            for doc in batch
        ]

        success, errors = helpers.bulk(
            client,
            actions,
            raise_on_error=False,
            stats_only=False,
        )
        failed = len(errors) if isinstance(errors, list) else 0
        total_success += int(success or 0)
        total_failed += failed

        print(
            f"Batch {batch_index}: attempted={len(actions)}, indexed={int(success or 0)}, failed={failed}"
        )

    return total_success, total_failed


def _switch_alias(client, alias_name: str, target_index: str):
    actions = []
    if client.indices.exists_alias(name=alias_name):
        existing = client.indices.get_alias(name=alias_name)
        for old_idx in existing.keys():
            actions.append({"remove": {"index": old_idx, "alias": alias_name}})
    actions.append({"add": {"index": target_index, "alias": alias_name}})
    client.indices.update_aliases({"actions": actions})


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Reindex AWS product catalog from MongoDB and/or JSON into OpenSearch with Bedrock embeddings"
    )
    parser.add_argument(
        "--source",
        choices=["mongo", "json", "both"],
        default="mongo",
        help="Source of product data",
    )
    parser.add_argument(
        "--json-file",
        default="final_combined.json",
        help="JSON input file path when --source json or both",
    )
    parser.add_argument(
        "--index-name",
        default=None,
        help="Override AWS_OPENSEARCH_INDEX",
    )
    parser.add_argument(
        "--mode",
        choices=["recreate", "versioned"],
        default="recreate",
        help="Recreate in-place, or create a versioned index",
    )
    parser.add_argument(
        "--alias",
        default=None,
        help="Optional alias name to point to the new index in versioned mode",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Bulk insert batch size",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max docs to process (0 means no limit)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and normalize docs only, without embedding or indexing",
    )
    return parser.parse_args()


def _merge_docs(primary: List[dict], secondary: List[dict]) -> List[dict]:
    merged: Dict[str, dict] = {}
    for doc in primary + secondary:
        doc_id = _as_str(doc.get("id"))
        if not doc_id:
            continue
        merged[doc_id] = doc
    return list(merged.values())


def _load_source_docs(args) -> List[dict]:
    json_docs: List[dict] = []
    mongo_docs: List[dict] = []

    if args.source in ("json", "both"):
        json_path = Path(args.json_file)
        if not json_path.is_absolute():
            json_path = Path(__file__).resolve().parent / json_path
        if not json_path.exists():
            raise FileNotFoundError(f"JSON input not found: {json_path}")
        json_docs = _load_docs_from_json(json_path)
        print(f"Loaded {len(json_docs)} docs from JSON: {json_path.name}")

    if args.source in ("mongo", "both"):
        mongo_docs = _load_docs_from_mongo()
        print(f"Loaded {len(mongo_docs)} docs from MongoDB")

    if args.source == "json":
        docs = json_docs
    elif args.source == "mongo":
        docs = mongo_docs
    else:
        docs = _merge_docs(mongo_docs, json_docs)

    if args.limit and args.limit > 0:
        docs = docs[: args.limit]

    if not docs:
        raise ValueError("No documents to index")
    return docs


def main():
    load_dotenv()
    args = _parse_args()

    region = _as_str(os.getenv("AWS_REGION"))
    embedding_model = _as_str(os.getenv("AWS_BEDROCK_EMBEDDING_MODEL"))
    if not region:
        raise ValueError("AWS_REGION is required")
    if not embedding_model:
        raise ValueError("AWS_BEDROCK_EMBEDDING_MODEL is required")

    opensearch = OpenSearchService()
    base_index = args.index_name or opensearch.index_name
    if not _as_str(base_index):
        raise ValueError("AWS_OPENSEARCH_INDEX is required")

    docs = _load_source_docs(args)
    print(f"Prepared {len(docs)} docs for indexing")

    if args.dry_run:
        print("Dry run complete. No embedding or indexing performed.")
        return

    vector_dimension = _apply_embeddings(docs, region=region, model_id=embedding_model)
    print(f"Embedding dimension detected: {vector_dimension}")

    if args.mode == "versioned":
        target_index = f"{base_index}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    else:
        target_index = base_index

    client = opensearch.client

    if args.mode == "recreate":
        print(f"Deleting existing index if present: {target_index}")
        _delete_index_if_exists(client, target_index)

    print(f"Creating index: {target_index}")
    _create_index(client, target_index, vector_dimension=vector_dimension)

    print(f"Bulk inserting {len(docs)} docs into {target_index}")
    total_success, total_failed = _bulk_insert(
        client,
        target_index,
        docs,
        batch_size=max(1, args.batch_size),
    )

    # Force refresh so count reflects recently indexed documents.
    client.indices.refresh(index=target_index)

    count_result = client.count(index=target_index)
    indexed_count = int(count_result.get("count", 0))
    print(f"Index count after load: {indexed_count}")

    print(f"Bulk summary: attempted={len(docs)}, indexed={total_success}, failed={total_failed}")

    if indexed_count < len(docs):
        print("Warning: indexed count is lower than prepared docs.")

    if args.mode == "versioned" and args.alias:
        _switch_alias(client, args.alias, target_index)
        print(f"Alias switched: {args.alias} -> {target_index}")

    print("Reindex completed.")
    print(f"Base index: {base_index}")
    print(f"Target index: {target_index}")
    print(f"Prepared docs: {len(docs)}")
    print(f"Indexed docs: {indexed_count}")


if __name__ == "__main__":
    main()
