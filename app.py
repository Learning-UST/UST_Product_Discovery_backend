from flask import Flask, request, jsonify
from search_service import AiSearch
from openai_service import OpenAIService
from embeddings import get_embedding
from voice_service import transcribe_audio
from agent_service import RetailAgentManager
from cosmos_service import CosmosService
from flask_cors import CORS
from config import get_config_value
import string

def _clean_query(q):
    return q.strip().rstrip(string.punctuation).strip() if q else q

import qrcode
import io
import base64
import requests as http_requests
from flask import send_file


app = Flask(__name__)
# This allows your Public IP to make requests to the Flask API
CORS(app, resources={r"/*": {"origins": ["http://20.63.27.178", "http://localhost:5173"]}})
# ✅ Initialize services (once)
ai_search = AiSearch()
openai_service = OpenAIService()
agent_manager = RetailAgentManager()
cosmos = CosmosService()

# ✅ Vector Search Endpoint
@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = _clean_query(data.get("query"))

    # embedding = get_embedding(query)
    results = ai_search.search_text(query, top_k=3)

    return jsonify({
        "query": query,
        "results": results
    })


# ✅ RAG Chat Endpoint
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    query = data.get("query")

    # embedding = get_embedding(query)
    docs = ai_search.search_text(query, top_k=3)
    answer = openai_service.generate_answer(query, docs)

    return jsonify({
        "query": query,
        "answer": answer,
        "sources": docs
    })

@app.route("/speech-to-text", methods=["POST"])
def stt():
    # Delegate to the token endpoint — frontend uses the key/region with the SDK directly
    return get_speech_token()

@app.route("/get-speech-token", methods=["GET"])
def get_speech_token():
    key = get_config_value("AZURE_SPEECH_KEY")
    region = get_config_value("AZURE_SPEECH_REGION")
    token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    resp = http_requests.post(token_url, headers={"Ocp-Apim-Subscription-Key": key}, verify=False)
    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch speech token"}), 502
    return jsonify({
        "token": resp.text,
        "region": region
    })


@app.route("/voice-query", methods=["POST"])
def voice_query():
    # 1. Receive audio and transcribe
    audio_file = request.files['audio']
    audio_file.save("temp.wav")
    user_text = transcribe_audio("temp.wav")
    
    # 2. Start Agentic Thread
    # The Agent Service manages the 'Thread' (conversation history) automatically
    client = agent_manager.project_client
    thread = client.agents.create_thread()
    client.agents.create_message(thread_id=thread.id, role="user", content=user_text)
    
    # 3. Run Agent (Agent decides to use Search or Cosmos tools)
    run = client.agents.create_and_process_run(thread_id=thread.id, agent_id="your_agent_id")
    
    # 4. Fetch final response
    messages = client.agents.list_messages(thread_id=thread.id)
    return jsonify({"answer": messages.data[0].content[0].text.value})

@app.route("/product-click/<upc>", methods=["GET"])
def handle_click(upc):
    """Instant retrieval endpoint for the Digital Twin clicks"""
    try:
        details = cosmos.get_enriched_product_info(upc)
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": "Product data incomplete", "details": str(e)}), 404
# Change the agent_query route to use the new Agentic logic
@app.route("/agent-query", methods=["POST"])
def agent_query():
    data = request.json
    query = _clean_query(data.get("query"))
    
    # This now calls the logic where the AI DECIDES which tool to use
    answer = openai_service.generate_agentic_answer(query)
    
    return jsonify({
        "query": query,
        "answer": answer
    })

@app.route("/get-shelf-twin/<shelf_id>", methods=["GET"])
def get_shelf_twin(shelf_id):
    layout = cosmos.get_shelf_layout(shelf_id)
    # This layout contains the 'rows' and 'products' your React grid needs
    return jsonify(layout)

@app.route("/product/direct/<upc>", methods=["GET"])
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

@app.route("/generate-qr/<shelf_id>", methods=["GET"])
def generate_qr(shelf_id):
    # This is the URL your phone will open. 
    # Change '192.168.x.x' to your computer's local IP address 
    # so your mobile phone can access your local React server.
    frontend_base_url = "http://20.63.27.178" 
    full_url = f"{frontend_base_url}/?shelfId={shelf_id}"
    
    # Generate the QR Code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(full_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save image to a memory buffer to send it via Flask
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')

@app.route("/products", methods=["GET"])
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

@app.route("/generate-shelf-qr/<shelf_id>", methods=["GET"])
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
    app.run(debug=True, port=5000)