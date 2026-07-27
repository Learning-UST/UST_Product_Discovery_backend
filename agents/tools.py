import json
from core.cloud_runtime import get_active_cloud_provider
from factory.resolver import Resolver
from utils.logger import get_logger

logger = get_logger()


class ProductSearchTools:

    def __init__(self, cloud_provider=None):
        self.cloud_provider = cloud_provider or get_active_cloud_provider()
        services = Resolver.resolve(self.cloud_provider)
        self.database = services["database"]
        self.llm = services["llm"]
        self.search = services["vectordb"]

    # ✅ Tool 3: Direct inventory price enrichment by UPC (AWS parity with Azure)
    def enrich_ai_results_with_prices(self, ai_result: dict) -> dict:
        """
        Mirrors the Azure logic:
          Azure  → OpenAI query_builder reads AI-search content (UPCs) and generates
                   a Cosmos SQL query against the inventory container.
          AWS    → We do the same explicitly: extract UPCs from AI search results,
                   query MongoDB inventory directly, and merge Price/US_Price back.

        This runs only on AWS. Azure already gets prices via its query_builder→Cosmos path.
        """
        if self.cloud_provider != "aws":
            return ai_result

        try:
            results = ai_result.get("results") if isinstance(ai_result, dict) else None
            if not isinstance(results, list) or not results:
                return ai_result

            # Extract UPCs from AI search results
            upcs = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                upc = item.get("upc") or item.get("UPC")
                if upc and str(upc).strip():
                    upcs.append(str(upc).strip())

            if not upcs:
                return ai_result

            # Direct inventory lookup by UPC (equivalent to Azure's Cosmos inventory query)
            get_inv = getattr(self.database, "get_inventory_by_upcs", None)
            if not callable(get_inv):
                return ai_result

            inventory_records = get_inv(upcs)
            if not inventory_records:
                return ai_result

            # Build UPC → inventory record map (normalise key to string)
            inv_map = {}
            for inv in inventory_records:
                if not isinstance(inv, dict):
                    continue
                upc_val = str(inv.get("UPC") or inv.get("upc") or "").strip()
                if upc_val:
                    inv_map[upc_val] = inv

            # Merge price/stock fields into each AI result item
            enriched_results = []
            for item in results:
                if not isinstance(item, dict):
                    enriched_results.append(item)
                    continue

                upc = str(item.get("upc") or item.get("UPC") or "").strip()
                inv = inv_map.get(upc)

                merged = dict(item)
                if isinstance(inv, dict):
                    if merged.get("price") is None:
                        merged["price"] = inv.get("Price") or inv.get("price")
                    if merged.get("us_price") is None:
                        merged["us_price"] = inv.get("US_Price") or inv.get("us_price")
                    if merged.get("discounted_price") is None:
                        merged["discounted_price"] = (
                            inv.get("Discounted_Price") or inv.get("discounted_price")
                        )
                    if merged.get("us_discounted_price") is None:
                        merged["us_discounted_price"] = (
                            inv.get("US_Discounted_Price") or inv.get("us_discounted_price")
                        )
                    if merged.get("stock") is None:
                        merged["stock"] = inv.get("Quantity") or inv.get("quantity")

                enriched_results.append(merged)

            enriched = dict(ai_result)
            enriched["results"] = enriched_results
            logger.info(f"[PRICE ENRICHMENT] Enriched {len(enriched_results)} AI results with inventory prices")
            return enriched

        except Exception as e:
            logger.warning(f"Price enrichment failed, returning original ai_result: {e}")
            return ai_result

    def enrich_ai_results_with_promotions(self, ai_result: dict) -> dict:
        """
        Step 2.75: Apply promotions and calculate discounted prices.
        
        For each product in ai_result:
        1. Look up applicable promotions (by Brand, Category, Product_Id)
        2. Calculate discounted price = base_price * (1 - discount_percentage / 100)
        3. Add promotion_name and us_discounted_price to the result
        
        This runs on AWS to mirror Azure's price resolution which includes promotion logic.
        On Azure, this is done via Cosmos query in resolve_effective_price.
        """
        if self.cloud_provider != "aws":
            return ai_result

        try:
            results = ai_result.get("results") if isinstance(ai_result, dict) else None
            if not isinstance(results, list) or not results:
                return ai_result

            # Get promotions for all products
            get_promos = getattr(self.database, "get_promotions_for_products", None)
            if not callable(get_promos):
                return ai_result

            promo_map = get_promos(results)
            if not promo_map:
                # No promotions found; return results with base prices as-is
                return ai_result

            # Apply promotions to each result
            enriched_results = []
            for item in results:
                if not isinstance(item, dict):
                    enriched_results.append(item)
                    continue

                merged = dict(item)

                # Try to match product by Product_Id, Brand, or Category
                product_id = str(merged.get("product_id") or merged.get("Product_Id") or "")
                brand = merged.get("brand") or merged.get("Brand")
                category = merged.get("category") or merged.get("Category")

                promo = None
                if product_id and product_id in promo_map:
                    promo = promo_map[product_id]
                elif brand and brand in promo_map:
                    promo = promo_map[brand]
                elif category and category in promo_map:
                    promo = promo_map[category]

                if promo:
                    merged["promotion"] = {
                        "name": promo.get("promotion_name"),
                        "discount_percentage": promo.get("discount_percentage"),
                    }

                    # Calculate discounted prices
                    base_price = merged.get("price")
                    us_base_price = merged.get("us_price")
                    discount_pct = promo.get("discount_percentage", 0) or 0

                    if base_price is not None:
                        try:
                            merged["discounted_price"] = round(
                                float(base_price) * (1.0 - float(discount_pct) / 100.0), 2
                            )
                        except (ValueError, TypeError):
                            pass

                    if us_base_price is not None:
                        try:
                            merged["us_discounted_price"] = round(
                                float(us_base_price) * (1.0 - float(discount_pct) / 100.0), 2
                            )
                        except (ValueError, TypeError):
                            pass

                enriched_results.append(merged)

            enriched = dict(ai_result)
            enriched["results"] = enriched_results
            logger.info(f"[PROMOTION ENRICHMENT] Applied promotions to {len(enriched_results)} results")
            return enriched

        except Exception as e:
            logger.warning(f"Promotion enrichment failed, returning original ai_result: {e}")
            return ai_result


    # ✅ Tool 1: Cosmos (Structured Search)
    def cosmos_query(self, query: str, content: str) -> dict:
        """
        Uses GPT → Cosmos DB query → structured filtering
        """

        try:
            logger.info(f"Received Cosmos query: {query}")
            query_response = self.llm.query_builder(query, content)
            logger.info(f"Query builder response: {json.dumps(query_response)}")

            if query_response["status"] != "success":
                return {
                    "status": "error",
                    "message": "Query builder failed",
                    "details": query_response
                }

            table = query_response["table"]

            db_result = self.database.query_executor(query_response, table)
            logger.info(f"Cosmos query result: {json.dumps(db_result)}")
            return {
                "status": "success",
                "source": "database",
                "table": table,
                "count": db_result.get("count", 0),
                "results": db_result.get("results", [])
            }

        except Exception as e:
            logger.exception("Cosmos query failed")
            return {
                "status": "error",
                "source": "database",
                "message": str(e)
            }

    # ✅ Tool 2: AI Search (Semantic Search)
    def ai_search_query(self, query: str) -> dict:
        """
        Uses Azure AI Search → semantic retrieval
        """

        try:
            logger.info(f"Received AI Search query: {query}")
            docs = self.search.search_text(query, top_k=5)

            return {
                "status": "success",
                "source": "ai_search",
                "count": len(docs) if docs else 0,
                "results": docs if docs else []
            }

        except Exception as e:
            logger.exception("AI Search failed")
            return {
                "status": "error",
                "source": "search",
                "message": str(e)
            }