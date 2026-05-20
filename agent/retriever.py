# retriever.py

from services.search_service import AiSearch
from utils.logger import get_logger
from utils.config import get_config_value

logger = get_logger()


class Retriever:

    def __init__(self):
        self.search = AiSearch()

    def _price_source(self):
        source = str(get_config_value("PRICE_SOURCE", "NORMAL")).strip().upper()
        return source if source in {"NORMAL", "US"} else "NORMAL"

    def _currency_symbol(self, source: str) -> str:
        configured_symbol = get_config_value("PRICE_CURRENCY_SYMBOL")
        if configured_symbol is not None and str(configured_symbol).strip() != "":
            return str(configured_symbol).strip()
        return "$" if source == "US" else "INR "

    def _format_currency(self, symbol: str, amount):
        if amount is None:
            return None
        return f"{symbol}{amount}"

    def _apply_price_source(self, docs):
        source = self._price_source()
        currency_symbol = self._currency_symbol(source)
        normalized_docs = []

        for doc in docs:
            d = dict(doc)
            normal_price = d.get("price")
            us_price = d.get("us_price", d.get("US_Price"))
            normal_discounted_price = d.get("discounted_price")
            us_discounted_price = d.get("us_discounted_price")

            selected_price = normal_price
            selected_discounted_price = normal_discounted_price

            if source == "US":
                selected_price = us_price if us_price is not None else normal_price
                selected_discounted_price = (
                    us_discounted_price
                    if us_discounted_price is not None
                    else normal_discounted_price
                )

            d["normal_price"] = normal_price
            d["normal_discounted_price"] = normal_discounted_price
            d["price_source"] = source
            d["currency_symbol"] = currency_symbol
            d["price"] = selected_price
            d["discounted_price"] = selected_discounted_price
            d["display_price"] = self._format_currency(currency_symbol, selected_price)
            d["display_discounted_price"] = self._format_currency(currency_symbol, selected_discounted_price)
            normalized_docs.append(d)

        return normalized_docs

    def retrieve(self, query: str, top_k=3):
        docs = self.search.search_text(query, top_k=top_k)

        # ✅ Retry strategy if no results
        if not docs:
            logger.info("No results found. Retrying with relaxed query...")
            relaxed_query = self._relax_query(query)
            docs = self.search.search_text(relaxed_query, top_k=top_k)

        return self._apply_price_source(docs)

    def _relax_query(self, query: str) -> str:
        # Basic fallback strategy
        return query.lower().replace("best", "").strip()