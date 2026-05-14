from agent.retriever import Retriever
from agent.prompt import build_context, build_prompt,format_history, SYSTEM_PROMPT
from agent.llm_service import LLMService
from agent.query_rewriter import QueryRewriter
from logger import get_logger

logger = get_logger()


class ShoppingAgent:

    def __init__(self):
        self.retriever = Retriever()
        self.llm = LLMService()
        self.rewriter = QueryRewriter()   # ✅ NEW

    def ask(self, query: str,history: list) :


        # ✅ Step 1: Get formatted history
        history = format_history(history)

        # ✅ Step 2: Rewrite query using history
        rewritten_query = self.rewriter.rewrite(query, history)

        logger.info(f"Original Query: {query}")
        logger.info(f"Rewritten Query: {rewritten_query}")

        # ✅ Step 3: Retrieve using rewritten query
        docs = self.retriever.retrieve(rewritten_query)

        # ✅ Step 4: Build context
        context = build_context(docs)

        # ✅ Step 5: Build final prompt (use ORIGINAL query for answering)
        prompt = build_prompt(query, history, context)

        # ✅ Step 6: Generate answer
        response = self.llm.generate(SYSTEM_PROMPT, prompt)

        return response , docs
