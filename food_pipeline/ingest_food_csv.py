import argparse
import csv
import json
import re
from typing import Dict, List

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import OpenAI

from utils.config import get_config_value



EXPECTED_COLUMNS = [
    "Recipe Number",
    "Recipe Name",
    "Short Name",
    "Station",
    "Menu Portion Size",
    "Menu Portion Weight(g)",
    "GTIN",
    "Sell Price",
    "Kcal/100g",
    "COLOR",
    "KCAL",
    "FAT (g)",
    "CHO (g)",
    "Total Sugars (g)",
    "PRO (g)",
]

NORMALIZED_OUTPUT_COLUMNS = [
    "id",
    "recipe_number",
    "recipe_name",
    "short_name",
    "station",
    "menu_portion_size",
    "menu_portion_weight_g",
    "gtin",
    "sell_price",
    "kcal_per_100g",
    "color",
    "kcal",
    "fat_g",
    "carbohydrates_g",
    "total_sugars_g",
    "protein_g",
    "nutrition_summary",
    "embedding_text",
]


def _clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_recipe_number(value) -> str:
    text = _clean_text(value)
    if text.startswith("'"):
        text = text[1:]
    return text.strip()


def _to_float(value):
    text = _clean_text(value)
    if not text:
        return None

    text = text.replace(",", "")
    text = text.replace("$", "")
    text = text.replace("+", "")
    text = text.strip()

    if text.lower() in {"na", "n/a", "null", "none", "#value!", "combo", "combo-"}:
        return None

    if text.lower().startswith("combo"):
        return None

    text = re.sub(r"\s+", "", text)

    try:
        return float(text)
    except ValueError:
        return None


def _safe_id_part(value: str) -> str:
    # Replace . with _ and remove all other forbidden characters
    value = (value or "").replace(".", "_")
    return re.sub(r"[^A-Za-z0-9_\-=]", "", value)


def _build_doc_id(recipe_number: str, gtin: str, row_index: int) -> str:
    rn = _safe_id_part(recipe_number)
    g = _safe_id_part(gtin)
    if rn and g:
        return f"food_{rn}_{g}"
    if rn:
        return f"food_{rn}_{row_index}"
    return f"food_row_{row_index}"


def _normalize_row(raw: Dict[str, str], row_index: int) -> Dict:
    row = {col: raw.get(col, "") for col in EXPECTED_COLUMNS}

    recipe_number = _clean_recipe_number(row["Recipe Number"])
    recipe_name = _clean_text(row["Recipe Name"])
    short_name = _clean_text(row["Short Name"])
    station = _clean_text(row["Station"])
    menu_portion_size = _clean_text(row["Menu Portion Size"])
    gtin = _clean_text(row["GTIN"])
    color = _clean_text(row["COLOR"]).upper()

    if not recipe_number and not recipe_name:
        return {}

    menu_portion_weight_g = _to_float(row["Menu Portion Weight(g)"])
    sell_price = _to_float(row["Sell Price"])
    kcal_per_100g = _to_float(row["Kcal/100g"])
    kcal = _to_float(row["KCAL"])
    fat_g = _to_float(row["FAT (g)"])
    carbohydrates_g = _to_float(row["CHO (g)"])
    total_sugars_g = _to_float(row["Total Sugars (g)"])
    protein_g = _to_float(row["PRO (g)"])

    nutrition_summary = (
        f"Kcal/100g: {kcal_per_100g if kcal_per_100g is not None else 'NA'}, "
        f"Kcal: {kcal if kcal is not None else 'NA'}, "
        f"Fat (g): {fat_g if fat_g is not None else 'NA'}, "
        f"Carbohydrates (g): {carbohydrates_g if carbohydrates_g is not None else 'NA'}, "
        f"Sugars (g): {total_sugars_g if total_sugars_g is not None else 'NA'}, "
        f"Protein (g): {protein_g if protein_g is not None else 'NA'}"
    )

    embedding_text = (
        f"Recipe {recipe_name}. Short name {short_name}. Station {station}. "
        f"Portion {menu_portion_size} with weight {menu_portion_weight_g if menu_portion_weight_g is not None else 'NA'} grams. "
        f"Sell price {sell_price if sell_price is not None else 'NA'} dollars. "
        f"Color tag {color or 'NA'}. {nutrition_summary}."
    )

    return {
        "id": _build_doc_id(recipe_number, gtin, row_index),
        "recipe_number": recipe_number,
        "recipe_name": recipe_name,
        "short_name": short_name,
        "station": station,
        "menu_portion_size": menu_portion_size,
        "menu_portion_weight_g": menu_portion_weight_g,
        "gtin": gtin,
        "sell_price": sell_price,
        "kcal_per_100g": kcal_per_100g,
        "color": color,
        "kcal": kcal,
        "fat_g": fat_g,
        "carbohydrates_g": carbohydrates_g,
        "total_sugars_g": total_sugars_g,
        "protein_g": protein_g,
        "nutrition_summary": nutrition_summary,
        "embedding_text": embedding_text,
    }


def _load_food_docs(csv_path: str) -> List[Dict]:
    docs = []

    with open(csv_path, "r", encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f)
        for i, raw_row in enumerate(reader, start=1):
            doc = _normalize_row(raw_row, i)
            if doc:
                docs.append(doc)

    return docs


def _write_cleaned_csv(output_path: str, docs: List[Dict]):
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=NORMALIZED_OUTPUT_COLUMNS)
        writer.writeheader()
        for d in docs:
            row = {k: d.get(k) for k in NORMALIZED_OUTPUT_COLUMNS}
            writer.writerow(row)


def _get_clients(index_name_override=None):
    search_endpoint = get_config_value("FOOD_AZURE_SEARCH_ENDPOINT") or get_config_value("AZURE_SEARCH_ENDPOINT")
    search_key = get_config_value("FOOD_AZURE_SEARCH_API_KEY") or get_config_value("AZURE_SEARCH_API_KEY")
    index_name = (
        index_name_override
        or get_config_value("FOOD_AZURE_SEARCH_INDEX")
        or "shopilot_food_recipes"
    )

    aoai_endpoint = get_config_value("FOOD_AZURE_OPENAI_ENDPOINT") or get_config_value("AZURE_OPENAI_ENDPOINT")
    aoai_key = get_config_value("FOOD_AZURE_OPENAI_API_KEY") or get_config_value("AZURE_OPENAI_API_KEY")
    embedding_model = (
        get_config_value("FOOD_AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        or get_config_value("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    )

    missing = []
    if not search_endpoint:
        missing.append("FOOD_AZURE_SEARCH_ENDPOINT or AZURE_SEARCH_ENDPOINT")
    if not search_key:
        missing.append("FOOD_AZURE_SEARCH_API_KEY or AZURE_SEARCH_API_KEY")
    if not index_name:
        missing.append("FOOD_AZURE_SEARCH_INDEX")
    if not aoai_endpoint:
        missing.append("FOOD_AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_ENDPOINT")
    if not aoai_key:
        missing.append("FOOD_AZURE_OPENAI_API_KEY or AZURE_OPENAI_API_KEY")
    if not embedding_model:
        missing.append("FOOD_AZURE_OPENAI_EMBEDDING_DEPLOYMENT or AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

    if missing:
        raise ValueError(f"Missing config: {', '.join(missing)}")

    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(search_key),
    )

    openai_client = OpenAI(
        base_url=f"{aoai_endpoint}/openai/v1",
        api_key=aoai_key,
    )

    return search_client, openai_client, embedding_model


def _embed_docs(docs: List[Dict], openai_client: OpenAI, embedding_model: str, batch_size: int = 32):
    for start in range(0, len(docs), batch_size):
        batch = docs[start:start + batch_size]
        inputs = [d["embedding_text"] for d in batch]

        response = openai_client.embeddings.create(
            model=embedding_model,
            input=inputs,
        )

        for d, item in zip(batch, response.data):
            d["vector"] = item.embedding


def _upload_docs(search_client: SearchClient, docs: List[Dict], upload_batch_size: int = 200):
    total_success = 0
    total_failed = 0

    for start in range(0, len(docs), upload_batch_size):
        batch = docs[start:start + upload_batch_size]
        result = search_client.upload_documents(documents=batch)
        for r in result:
            if r.succeeded:
                total_success += 1
            else:
                total_failed += 1

    return total_success, total_failed


def main():
    parser = argparse.ArgumentParser(description="Ingest food CSV into Azure AI Search with vectors")
    parser.add_argument(
        "--csv-file",
        default="food.csv",
        help="Path to food CSV file (default: food.csv)",
    )
    parser.add_argument(
        "--index-name",
        default=None,
        help="Override index name",
    )
    parser.add_argument(
        "--dump-json",
        default=None,
        help="Optional path to dump normalized docs before embedding/upload",
    )
    parser.add_argument(
        "--clean-output-csv",
        default="food.cleaned.csv",
        help="Path to write cleaned/normalized CSV output (default: food.cleaned.csv)",
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Only parse and clean CSV and write outputs; skip embedding and upload",
    )
    args = parser.parse_args()

    docs = _load_food_docs(args.csv_file)
    if not docs:
        raise ValueError("No valid rows found in CSV.")

    if args.clean_output_csv:
        _write_cleaned_csv(args.clean_output_csv, docs)
        print(f"Wrote cleaned CSV: {args.clean_output_csv}")

    if args.dump_json:
        with open(args.dump_json, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2)
        print(f"Wrote normalized docs: {args.dump_json}")

    if args.clean_only:
        print(f"Cleaning completed. rows={len(docs)}")
        return

    search_client, openai_client, embedding_model = _get_clients(index_name_override=args.index_name)

    print(f"Loaded {len(docs)} docs from CSV")
    print(f"Embedding with model: {embedding_model}")

    _embed_docs(docs, openai_client, embedding_model)

    success, failed = _upload_docs(search_client, docs)
    print(f"Upload completed. succeeded={success}, failed={failed}")

    if failed:
        raise RuntimeError(f"Some documents failed to upload: {failed}")


if __name__ == "__main__":
    main()
