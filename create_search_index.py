import argparse
from pathlib import Path
import json

from services.search_service import AiSearch


def _is_missing_id(value):
    return value is None or str(value).strip() == ""


def _generate_doc_id(doc: dict, idx: int) -> str:
    product_id = doc.get("product_id")
    shelf_id = doc.get("shelf_id")
    row_id = doc.get("row_id")

    parts = ["AUTO"]
    if product_id is not None:
        parts.append(f"P{product_id}")
    if shelf_id is not None:
        parts.append(f"S{shelf_id}")
    if row_id is not None:
        parts.append(f"R{row_id}")
    parts.append(f"IDX{idx}")
    return "_".join(parts)


def _load_and_prepare_docs(input_path: Path, auto_generate_missing_ids: bool):
    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError("Input JSON must be an array of documents")

    missing = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        if _is_missing_id(item.get("id")):
            if auto_generate_missing_ids:
                item["id"] = _generate_doc_id(item, idx)
            else:
                missing.append((
                    idx,
                    item.get("product_name") or item.get("name"),
                    item.get("product_id"),
                    item.get("shelf_id"),
                    item.get("row_id"),
                ))

    if missing:
        print("Found documents with missing id:")
        for idx, name, product_id, shelf_id, row_id in missing:
            print(
                f"  idx0={idx} product={name} product_id={product_id} shelf_id={shelf_id} row_id={row_id}"
            )
        raise ValueError("Upload blocked: one or more documents have missing id")

    temp_input = input_path.with_name(f"{input_path.stem}.with_ids{input_path.suffix}")
    with open(temp_input, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)

    return temp_input


def main():
    parser = argparse.ArgumentParser(
        description="Create Azure AI Search index and upload documents from a JSON file"
    )
    parser.add_argument(
        "--input-file",
        default="final_combined.json",
        help="Input JSON file path (default: final_combined.json)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete the existing index first, then create it again",
    )
    parser.add_argument(
        "--no-auto-generate-missing-ids",
        action="store_true",
        help="Fail if any document id is missing instead of auto-generating",
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.is_absolute():
        input_path = Path(__file__).resolve().parent / input_path

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    ai_search = AiSearch()

    if args.recreate:
        try:
            ai_search.index_client.delete_index(ai_search.index_name)
            print(f"Deleted existing index: {ai_search.index_name}")
        except Exception as exc:
            print(f"Skip delete (index may not exist): {exc}")

    ai_search.create_index()

    prepared_input = _load_and_prepare_docs(
        input_path,
        auto_generate_missing_ids=not args.no_auto_generate_missing_ids,
    )

    docs = ai_search.read_json(str(prepared_input))
    print(f"Prepared {len(docs)} docs from {prepared_input.name}")

    result = ai_search.insert(docs)
    if result is None:
        raise RuntimeError("Upload failed. See previous error details from Azure Search.")

    print("Index creation and data upload completed.")


if __name__ == "__main__":
    main()
