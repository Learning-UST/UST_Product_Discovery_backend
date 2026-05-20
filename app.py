from flask import Flask, request, jsonify
from services.search_service import AiSearch
from services.openai_service import OpenAIService
from services.agent_service import ShoppingAgent
from services.voice_service import transcribe_audio
from services.cosmos_service import CosmosService
from flask_cors import CORS
from utils.config import get_config_value
import string
from utils.logger import get_logger
from agents.agent import ShopilotAgent

import qrcode
import io
import requests as http_requests
from flask import send_file

logger=get_logger()
app = Flask(__name__)

cors_origins = get_config_value("CORS_ALLOWED_ORIGINS", "*")
if isinstance(cors_origins, str) and "," in cors_origins:
    cors_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# ✅ Initialize services (once)
ai_search = AiSearch()
agent=ShoppingAgent()
shopilot=ShopilotAgent()
openai_service = OpenAIService()
try:
    agent_manager = ShoppingAgent()
except Exception:
    agent_manager = None
cosmos = CosmosService()


def _clean_query(q):
    return q.strip().rstrip(string.punctuation).strip() if q else q


@app.route("/api/search", methods=["POST"])
def search():
    data = request.json
    query = _clean_query(data.get("query"))

    # embedding = get_embedding(query)
    results = ai_search.search_text(query, top_k=3)

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
    answer,docs = shopilot.chat(message=query, history=history)
    return jsonify({
        "query": query,
        "answer": answer,
        "sources": docs
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


@app.route("/api/voice-query", methods=["POST"])
def voice_query():
    if agent_manager is None:
        return jsonify({"error": "Agent service is not configured"}), 503

    import tempfile
    audio_file = request.files['audio']
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tmp:
        audio_file.save(tmp.name)
        user_text = transcribe_audio(tmp.name)

    # 2. Start Agentic Thread
    client = agent_manager.project_client
    thread = client.agents.create_thread()
    client.agents.create_message(thread_id=thread.id, role="user", content=user_text)

    # 3. Run Agent (Agent decides to use Search or Cosmos tools)
    agent_id = get_config_value("AGENT_ID")
    if not agent_id:
        return jsonify({"error": "AGENT_ID is missing in configuration"}), 500
    run = client.agents.create_and_process_run(thread_id=thread.id, agent_id=agent_id)

    # 4. Fetch final response
    messages = client.agents.list_messages(thread_id=thread.id)
    return jsonify({"answer": messages.data[0].content[0].text.value})

@app.route("/api/product-click/<upc>", methods=["GET"])
def handle_click(upc):
    """Instant retrieval endpoint for the Digital Twin clicks"""
    try:
        details = cosmos.get_enriched_product_info(upc)
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": "Product data incomplete", "details": str(e)}), 404
@app.route("/api/agent-query", methods=["POST"])
def agent_query():
    data = request.json
    query = _clean_query(data.get("query"))
    
    # This now calls the logic where the AI DECIDES which tool to use
    answer = openai_service.generate_agentic_answer(query)
    
    return jsonify({
        "query": query,
        "answer": answer
    })

@app.route("/api/get-shelf-twin/<shelf_id>", methods=["GET"])
def get_shelf_twin(shelf_id):
    layout = cosmos.get_shelf_layout(shelf_id)
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
        product_info = cosmos.get_enriched_product_info(str(upc))
        
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
        products = cosmos.get_all_products()
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

@app.route("/api/product/name/<porodcut_name>", methods=["GET"])
def get_product(porodcut_name):
    """
    FAST PATH: Called when a user selects a product on the Digital Twin.
    Returns metadata + current stock + calculated final price instantly.
    """
    try:
        # This uses the 'enriched' method we built in CosmosService
        # It handles: 1. Metadata 2. Inventory 3. Promotion Logic
        product_info = cosmos.get_product_by_name(str(porodcut_name))
        
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
        layout = cosmos.get_shelf_layout(shelf_id)
        
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