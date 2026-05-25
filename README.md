# UST_Product_Discovery_backend

## Cloud Provider Switching

The backend supports runtime switching between Azure and AWS without changing endpoint URLs.

- Default provider is read from `CLOUD_PROVIDER` on startup.
- Frontend can switch provider at runtime via `POST /api/set-agent` with:
	- `{ "cloud_provider": "azure" }`
	- `{ "cloud_provider": "aws" }`
- The selected provider remains active for all requests until `/api/set-agent` is called again.

## Required AWS Environment Variables

Add these to `.env` for AWS mode:

- `AWS_REGION`
- `AWS_BEDROCK_REGION`
- `AWS_BEDROCK_CHAT_MODEL`
- `AWS_BEDROCK_EMBEDDING_MODEL`
- `AWS_TRANSCRIBE_REGION`
- `AWS_STS_DURATION_SECONDS`
- `AWS_OPENSEARCH_HOST`
- `AWS_OPENSEARCH_INDEX`
- `AWS_OPENSEARCH_USERNAME` (optional)
- `AWS_OPENSEARCH_PASSWORD` (optional)
- `AWS_MONGODB_URI`
- `AWS_MONGODB_DB_NAME`
- `AWS_MONGODB_PRODUCTS_COLLECTION`
- `AWS_MONGODB_INVENTORY_COLLECTION`
- `AWS_MONGODB_PROMOTION_COLLECTION`
- `AWS_MONGODB_LAYOUT_COLLECTION`