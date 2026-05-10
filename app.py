from flask import Flask, request, jsonify
from search_service import AiSearch
from openai_service import OpenAIService
from embeddings import get_embedding

app = Flask(__name__)

# ✅ Initialize services (once)
ai_search = AiSearch()
openai_service = OpenAIService()


# ✅ Vector Search Endpoint
@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = data.get("query")

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


if __name__ == "__main__":
    app.run(debug=True, port=5000)