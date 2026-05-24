from flask import Flask, request, jsonify
from flask_cors import CORS
from utils.config import get_config_value
import string
import re
from utils.logger import get_logger
from agents.agent import ShopilotAgent
from factory.resolver import Resolver
import qrcode
import io
import requests as http_requests
from flask import send_file
from flask import g


logger=get_logger()
app = Flask(__name__)

cors_origins = get_config_value("CORS_ALLOWED_ORIGINS", "*")
if isinstance(cors_origins, str) and "," in cors_origins:
    cors_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

_active_cloud_provider = str(get_config_value("CLOUD_PROVIDER", "azure")).strip().lower()
_active_services = None


def _configure_services(cloud_provider):
    global _active_services, _active_cloud_provider
    provider = str(cloud_provider or "azure").strip().lower()
    services = Resolver.resolve(provider)
    _active_services = {
        "llm_service": services["llm"],
        "vectordb_service": services["vectordb"],
        "database_service": services["database"],
        "agent": ShopilotAgent()
    }
    _active_cloud_provider = provider


def _ensure_services():
    global _active_services
    if _active_services is None:
        _configure_services(_active_cloud_provider)
    return _active_services


@app.before_request
def _bind_request_services():
    services = _ensure_services()
    g.llm_service = services["llm_service"]
    g.vectordb_service = services["vectordb_service"]
    g.database_service = services["database_service"]
    g.agent = services["agent"]


def _clean_query(q):
    return q.strip().rstrip(string.punctuation).strip() if q else q


def _normalize_product_id(raw_id):
    if raw_id is None:
        return ""

    # UPC/SKU normalization: collapse whitespace and keep only safe identifier chars.
    normalized = re.sub(r"\s+", "", str(raw_id))
    normalized = re.sub(r"[^A-Za-z0-9_-]", "", normalized)
    return normalized


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Shopilot Agent is running!"})

@app.route("/api/set-agent", methods=["POST"])
def set_agent():
    data = request.json
    cloud_provider = data.get("cloud_provider", "azure")

    try:
        # Resolve services
        _configure_services(cloud_provider)

        return jsonify({
            "status": "ok",
            "message": "Agent configured!",
            "cloud_provider": _active_cloud_provider
        })

    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400


@app.route("/api/search", methods=["POST"])
def search():
    data = request.json
    query = _clean_query(data.get("query"))

    # embedding = get_embedding(query)
    results = g.vectordb_service.search_text(query, top_k=3)

    return jsonify({
        "query": query,
        "results": results
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    query = data.get("query")
    history = data.get("messages")
    # embedding = get_embedding(query)
    # docs = ai_search.search_text(query, top_k=3)
    # answer = openai_service.generate_answer(query, history, docs)
    answer, docs, mentioned_records = g.agent.chat(message=query, history=history)
    product_upcs = []
    seen = set()

    for item in mentioned_records or []:
        if not isinstance(item, dict):
            continue

        raw_upc = item.get("upc") or item.get("product_upc") or item.get("id") or item.get("sku")
        if raw_upc is None:
            continue

        upc = _normalize_product_id(raw_upc)
        if upc and upc not in seen:
            seen.add(upc)
            product_upcs.append(upc)

    return jsonify({
        "query": query,
        "answer": answer,
        "sources": docs,
        "product_upcs": product_upcs
    })

@app.route("/api/speech-to-text", methods=["POST"])
def stt():
    # Delegate to the token endpoint — frontend uses the key/region with the SDK directly
    return get_speech_token()

@app.route("/api/get-speech-token", methods=["GET"])
def get_speech_token():
    key = get_config_value("AZURE_SPEECH_KEY")
    region = get_config_value("AZURE_SPEECH_REGION")
    token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    resp = http_requests.post(token_url, headers={"Ocp-Apim-Subscription-Key": key})
    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch speech token"}), 502
    return jsonify({
        "token": resp.text,
        "region": region
    })


@app.route("/api/product-click/<upc>", methods=["GET"])
def handle_click(upc):
    """Instant retrieval endpoint for the Digital Twin clicks"""
    try:
        details = g.database_service.get_enriched_product_info(upc)
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": "Product data incomplete", "details": str(e)}), 404
@app.route("/api/agent-query", methods=["POST"])
def agent_query():
    data = request.json
    query = _clean_query(data.get("query"))

    # Prefer legacy agentic method when available; fallback to regular chat flow.
    if hasattr(g.llm_service, "generate_agentic_answer"):
        answer = g.llm_service.generate_agentic_answer(query)
    else:
        history = data.get("messages") or []
        answer, _, _ = g.agent.chat(message=query, history=history)
    
    return jsonify({
        "query": query,
        "answer": answer
    })

@app.route("/api/get-shelf-twin/<shelf_id>", methods=["GET"])
def get_shelf_twin(shelf_id):
    layout = g.database_service.get_shelf_layout(shelf_id)
    # This layout contains the 'rows' and 'products' your React grid needs
    return jsonify(layout)

@app.route("/api/product/direct/<upc>", methods=["GET"])
def get_direct_product(upc):
    """
    FAST PATH: Called when a user selects a product on the Digital Twin.
    Returns metadata + current stock + calculated final price instantly.
    """
    try:
        # This uses the 'enriched' method we built in CosmosService
        # It handles: 1. Metadata 2. Inventory 3. Promotion Logic
        product_info = g.database_service.get_enriched_product_info(str(upc))
        
        return jsonify({
            "status": "success",
            "data": product_info
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Product not found or data incomplete",
            "error": str(e)
        }), 404

@app.route("/api/generate-qr/<shelf_id>", methods=["GET"])
def generate_qr(shelf_id):
    frontend_base_url = get_config_value("FRONTEND_BASE_URL", "http://localhost:5173")
    full_url = f"{frontend_base_url}/?shelfId={shelf_id}"

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(full_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return send_file(img_io, mimetype='image/png')

@app.route("/api/products", methods=["GET"])
def get_all_products():
    """Returns all products from the products Cosmos DB container."""
    try:
        products = g.database_service.get_all_products()
        return jsonify({
            "status": "success",
            "count": len(products),
            "data": products
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Unable to fetch products",
            "error": str(e)
        }), 500

@app.route("/api/product/name/<product_name>", methods=["GET"])
def get_product(product_name):
    """
    FAST PATH: Called when a user selects a product on the Digital Twin.
    Returns metadata + current stock + calculated final price instantly.
    """
    try:
        # Return enriched product details (includes pricing and promotion fields).
        product_info = g.database_service.get_enriched_product_info_by_name(str(product_name))

        if not product_info:
            return jsonify({
                "status": "error",
                "message": "Product not found"
            }), 404
        
        return jsonify({
            "status": "success",
            "data": product_info
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Product not found or data incomplete",
            "error": str(e)
        }), 404



@app.route("/api/generate-shelf-qr/<shelf_id>", methods=["GET"])
def get_shelf_qr(shelf_id):
    """
    Generates a QR code for a specific shelf.
    Can be used by store staff to print new shelf labels.
    """
    try:
        # 1. Verify shelf exists in Cosmos (Optional but good for data integrity)
        layout = g.database_service.get_shelf_layout(shelf_id)
        
        # 2. Generate QR Data
        # In a real app, this would be a deep link: https://retail-app.com/shelf/15
        qr_content = f"SHELF_ID_{shelf_id}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_content)
        qr.make(fit=True)
        
        # 3. Create image in memory
        img = qr.make_image(fill_color="black", back_color="white")
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        # 4. Return as a streamable file
        return send_file(img_io, mimetype='image/png')

    except Exception as e:
        return jsonify({"error": "Shelf not found", "details": str(e)}), 404

if __name__ == "__main__":
    app.run(
        host=get_config_value("FLASK_HOST", "127.0.0.1"),
        port=int(get_config_value("FLASK_PORT", 5000)),
        debug=bool(get_config_value("FLASK_DEBUG", False))
    )