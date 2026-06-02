from food_pipeline.cosmos_service import FoodCosmosService
from food_pipeline.food_search_service import FoodSearchService
from services.openai_service import OpenAIService
from agents.query_rewriter import QueryRewriter
from utils.logger import get_logger
import json

logger = get_logger("FoodAgent")


FOOD_SYSTEM_PROMPT  = """
You are a highly accurate and helpful food and recipe assistant.
Response Style:
- Always respond in clear, concise bullet points.
- Start with a bold key statement (main takeaway).
- Keep answers short, structured, and easy to read.
- Do not include unnecessary explanations.

Data Usage Rules:
- Use ONLY the provided context.
- Do NOT assume, guess, or hallucinate information.
- If data is missing, do not fabricate values.

Highlighting Rules:
- Always bold:
  - Recipe names
  - Calories (kcal)
  - Protein values
  - Any key value relevant to the user's query

Health Classification :
Use the "color" field to guide responses:

- GREEN  → Healthy (best choice)
- YELLOW → Moderate (okay occasionally)
- ORANGE → Less healthy (limit intake)
- RED    → Unhealthy (avoid if possible)

When recommending food:
- Prefer GREEN first
- Then YELLOW
- Avoid RED unless specifically asked

Recommendations:
- Suggest only items present in the context
- Bold the recipe names
- Explain briefly why they match (e.g., high protein, low calorie)
"""


QUERY_BUILDER_SYSTEM_PROMPT = """
You are an expert Cosmos DB query builder.

Your task:
1. Understand the user request
2. Generate a SAFE parameterized Cosmos SQL query
3. You will also receive context from an AI search tool — use it to refine the query

--------------------------------------------------

Strict Rules:
- Always use: SELECT * FROM c
- Always use: TOP 20
- NEVER inline values → always use parameters (@p1, @p2...)
- Use CONTAINS(c.field, @p) for text search
- Use direct comparisons for numeric fields
- ALWAYS include partition_key when filtering on 'station'
- Ensure queries are efficient and valid

--------------------------------------------------

Schema: recipe

Fields:
id, recipe_number, recipe_name, short_name, station,
menu_portion_size, menu_portion_weight_g, gtin,
sell_price, kcal_per_100g, color, kcal, fat_g,
carbohydrates_g, total_sugars_g, protein_g

--------------------------------------------------

Field Intelligence:

- recipe_name / short_name → text search fields
- station → PARTITION KEY (must include partition_key if filtered)
- sell_price → numeric filtering
- kcal → calories (lower = healthier)
- protein_g → protein (higher = better for fitness)
- fat_g, carbohydrates_g → macro filters

--------------------------------------------------

IMPORTANT: COLOR FIELD (Health Classification)

The 'color' field represents how healthy the food is:

- GREEN  → Healthy ✅ (low calorie, balanced nutrition)
- YELLOW → Moderate ⚖️ (okay in moderation)
- ORANGE → Less healthy ⚠️ (higher fat/carbs)
- RED    → Unhealthy ❌ (high fat, sugar, or calories)

Use this intelligently in queries:

Examples:
- Healthy food → c.color = "GREEN"
- Avoid unhealthy → c.color != "RED"
- Balanced → c.color IN ("GREEN", "YELLOW")

--------------------------------------------------

Query Patterns:

User intent → Query logic:

- "healthy food"
  → filter color = GREEN

- "high protein"
  → c.protein_g > @p1

- "low calorie"
  → c.kcal < @p1

- "cheap"
  → c.sell_price < @p1

- "garlic bread"
  → CONTAINS(c.recipe_name, @p1)

--------------------------------------------------

Output Format (STRICT JSON ONLY):

{
  "query": "SELECT TOP 20 * FROM c WHERE ...",
  "parameters": [
    {"name": "@p1", "value": "..."}
  ],
  "partition_key": "value_if_applicable"
}

--------------------------------------------------

DO NOT:
- Do not return explanations
- Do not return anything other than JSON
- Do not inline values directly in query
"""



class FoodAgent:

    def __init__(self):
        self.retriever = FoodSearchService()
        self.llm = OpenAIService()
        self.query_rewriter = QueryRewriter()
        self.cosmos_service = FoodCosmosService()

    # ✅ QUERY BUILDER
    def query_builder(self, message: str, content: str = "") -> dict:
        try:
            response = self.llm.generate(
                system_prompt=QUERY_BUILDER_SYSTEM_PROMPT,
                user_prompt=message + "\n\nContext:\n" + content
            )

            logger.info(f"Query Builder LLM Response : {response}")

            try:
                query_data = json.loads(response)
            except Exception:
                logger.error(f"Invalid JSON from LLM: {response}")
                return {"status": "error"}

            if not query_data.get("query"):
                return {"status": "error"}

            return {
                "status": "success",
                "query": query_data["query"],
                "parameters": query_data.get("parameters", []),
                "partition_key": query_data.get("partition_key")
            }

        except Exception as e:
            logger.exception("Query builder failed")
            return {"status": "error", "message": str(e)}

    # ✅ MAIN AGENT FLOW
    def chat_agentic(self, query, history=None, top_k=5):
        logger.info(f"Received query: {query}")
        # 1. Rewrite
        rewritten_query = self.query_rewriter.rewrite(query, history)
        logger.info(f"Rewritten query: {rewritten_query}")
        # 2. Vector Search
        docs = self.retriever.search(rewritten_query, top_k=top_k)
        logger.info(f"Retrieved {len(docs)} documents from search")
        logger.info(f"Search results: {docs}")
        # 3. Build Cosmos Query
        cosmos_query = self.query_builder(
            rewritten_query,
            content="\n".join([d['recipe_name'] for d in docs])
        )

        logger.info(f"Generated Cosmos Query: {cosmos_query}")

        # 4. Execute Cosmos Query
        if cosmos_query.get("status") == "success":
            result = self.cosmos_service.query_executor(cosmos_query)
        else:
            result = {"results": []}

        logger.info(f"Cosmos Query Result: {result}")

        # 5. Build Context
        context = self._build_context(docs, result.get("results", []))
        logger.info(f"Built context for LLM:\n{context}")
        # 6. Generate Answer
        prompt = self._build_prompt(rewritten_query, history, context)
        raw_answer = self.llm.generate(FOOD_SYSTEM_PROMPT, prompt)

        answer = self._format_answer(raw_answer)

        # 7. Extract referenced recipes
        mentioned_records = self._extract_mentioned_source_records(answer, docs)

        return answer, docs, mentioned_records

    # ✅ CLEAN CONTEXT (DEDUPLICATED)
    def _build_context(self, docs, query_results):
        seen = set()
        lines = []

        for item in docs + query_results:
            item_id = item.get("id")

            # ✅ Deduplicate
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)

            # ✅ Safe extraction with defaults
            recipe_name = item.get("recipe_name", "Unknown")
            protein = item.get("protein_g", "N/A")
            carbs = item.get("carbohydrates_g", "N/A")
            fat = item.get("fat_g", "N/A")
            kcal = item.get("kcal", "N/A")
            color = item.get("color", "N/A")
            price = item.get("sell_price", "N/A")
            station = item.get("station", "N/A")

            # ✅ Rich structured context (LLM-friendly)
            lines.append(
                f"Recipe: {recipe_name} | "
                f"Station: {station} | "
                f"Price: {price} | "
                f"Calories: {kcal} | "
                f"Protein: {protein}g | "
                f"Carbs: {carbs}g | "
                f"Fat: {fat}g | "
                f"Health: {color}"
            )

        return "\n".join(lines)

    # ✅ PROMPT BUILDER
    def _build_prompt(self, query, history, context):
        history_text = "\n".join(
            [f"{m['role']}: {m['content']}" for m in (history or [])]
        )

        return f"""
Conversation History:
{history_text}

Context:
{context}

User Question:
{query}

Answer:
"""

    # ✅ FORMAT RESPONSE
    def _format_answer(self, raw_answer):
        if not raw_answer:
            return ""

        # handle object vs string
        text = raw_answer if isinstance(raw_answer, str) else raw_answer.choices[0].message.content

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            return text

        main = lines[0]
        rest = lines[1:]

        formatted = f"**{main}**"
        if rest:
            formatted += "\n" + "\n".join([f"- {r}" for r in rest])

        return formatted

    # ✅ FIND MENTIONED RECIPES
    def _extract_mentioned_source_records(self, answer, docs):
        if not answer or not docs:
            return []

        mentioned = set()

        for d in docs:
            for key in ("recipe_name", "short_name"):
                val = d.get(key)
                if val and val.lower() in answer.lower():
                    mentioned.add(val)

        return [
            d for d in docs
            if d.get("recipe_name") in mentioned
            or d.get("short_name") in mentioned
        ]