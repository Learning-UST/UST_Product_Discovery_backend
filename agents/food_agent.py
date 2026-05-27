from services.food_search_service import FoodSearchService
from services.openai_service import OpenAIService

FOOD_SYSTEM_PROMPT = """
You are a highly accurate and helpful food and recipe assistant.

Instructions:
- Always answer in clear, concise bullet points (pointers).
- For each answer, make the most important information (from the user's query perspective) **bold** using markdown.
- Use only the provided context for facts—do not invent or assume information.
- If the user asks about nutrition (protein, carbs, calories, etc.), use the exact values from the data and bold the key numbers.
- If the user asks for recommendations, suggest recipes from the context and bold the recipe names.
- If the user asks about portion size or weight, include the "Menu Portion Size" and "Menu Portion Weight(g)" fields from the context in your answer, and bold these values. Do not include these fields unless the query is about portion size or weight.
- If the user refers to "it" or "that", resolve using the conversation history.
- Focus on high-level accuracy and clarity. Avoid unnecessary details.
- Be friendly and professional.
"""

class FoodAgent:
    def chat_agentic(self, query, history=None, top_k=5):
        """
        Agentic flow: rewrite query, search food index, generate answer, extract mentioned records.
        Cosmos DB is NOT used. Only food index is used for context.
        """
        docs = self.retriever.search(query, top_k=top_k)
        context = self._build_context(docs)
        prompt = self._build_prompt(query, history, context)
        raw_answer = self.llm.generate(FOOD_SYSTEM_PROMPT, prompt)
        answer = self._format_answer(raw_answer)
        mentioned_records = self._extract_mentioned_source_records(answer, docs)
        return answer, docs, mentioned_records

    def _extract_mentioned_source_records(self, answer, docs):
        """
        Extracts records from docs whose recipe_name or short_name is mentioned in the answer.
        """
        if not answer or not docs:
            return []
        mentioned = set()
        # Find all recipe names mentioned in the answer (exact match, case-insensitive)
        for d in docs:
            for key in ("recipe_name", "short_name"):
                val = d.get(key)
                if val and val.lower() in answer.lower():
                    mentioned.add(val)
        # Return all docs whose recipe_name or short_name was mentioned
        return [d for d in docs if d.get("recipe_name") in mentioned or d.get("short_name") in mentioned]
    def __init__(self):
        self.retriever = FoodSearchService()
        self.llm = OpenAIService()

    def chat(self, query, history=None, top_k=5):
        docs = self.retriever.search(query, top_k=top_k)
        context = self._build_context(docs)
        prompt = self._build_prompt(query, history, context)
        raw_answer = self.llm.generate(FOOD_SYSTEM_PROMPT, prompt)
        answer = self._format_answer(raw_answer)
        return answer, docs

    def _format_answer(self, answer):
        """
        Formats the answer so that the main answer is bold and the rest is in bullet points.
        Assumes the first line is the main answer, and the rest are points.
        """
        if not answer:
            return answer
        lines = [line.strip() for line in answer.strip().split("\n") if line.strip()]
        if not lines:
            return answer
        main = lines[0]
        points = lines[1:]
        formatted = f"**{main}**"
        if points:
            formatted += "\n" + "\n".join([f"- {pt}" for pt in points])
        return formatted

    def _build_context(self, docs):
        lines = []
        for d in docs:
            lines.append(f"Recipe: {d['recipe_name']} | Protein: {d['protein_g']}g | Carbohydrates: {d['carbohydrates_g']}g | Fat: {d['fat_g']}g | Calories: {d['kcal']} | {d['nutrition_summary']}")
        return "\n".join(lines)

    def _build_prompt(self, query, history, context):
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in (history or [])])
        return f"""
Conversation History:
{history_text}

Context:
{context}

User Question:
{query}

Answer:
"""
