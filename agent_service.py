# from azure.ai.projects import AIProjectClient
# from azure.identity import DefaultAzureCredential
# from config import get_config_value

# class RetailAgentManager:
#     def __init__(self):
#         conn_str = get_config_value("AZURE_PROJECT_CONNECTION_STRING")
        
#         if not conn_str:
#             # Fallback if your teammate only gave you the endpoint
#             endpoint = get_config_value("AZURE_PROJECT_ENDPOINT")
#             if not endpoint:
#                 raise ValueError("Please set AZURE_PROJECT_CONNECTION_STRING in your .env file. "
#                                  "You can find this in the Azure AI Foundry Project Overview.")
            
#             # If using only endpoint, you'll need more manual config, 
#             # so the Connection String is highly recommended.
#             self.project_client = AIProjectClient(
#                 endpoint=endpoint,
#                 credential=DefaultAzureCredential(),
#                 subscription_id=get_config_value("AZURE_SUBSCRIPTION_ID"),
#                 resource_group_name=get_config_value("AZURE_RESOURCE_GROUP")
#             )
#         else:
#             # BEST WAY: Uses the connection string directly
#             self.project_client = AIProjectClient.from_connection_string(
#                 conn_str=conn_str,
#                 credential=DefaultAzureCredential()
#             )

import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from config import get_config_value

class RetailAgentManager:
    def __init__(self):
        # Your specific project endpoint from your snippet
        project_endpoint = "https://planogramai.services.ai.azure.com/api/projects/proj-planogram"
        # Initialize the Project Client directly
        self.project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential()
        )
        
        print("✅ Azure AI Project Client initialized successfully.")

    def create_retail_assistant(self):
        # Use the deployment name for the model you have in Foundry (e.g., 'gpt-4o')
        model_deployment = get_config_value("AZURE_OPENAI_DEPLOYMENT")
        
        agent = self.project_client.agents.create_agent(
            model=model_deployment,
            name="Retail-Assistant",
            instructions="You are a smart retail assistant. Help users find products and check stock.",
            # This is where we will attach the Cosmos DB and Search tools next
        )
        return agent
        
    def create_retail_agent(self):
        # This creates a persistent agent in Azure that knows how to use your Search index
        agent = self.project_client.agents.create_agent(
            model=get_config_value("AZURE_OPENAI_DEPLOYMENT"),
            name="Retail-Assistant-Agent",
            instructions="You are a retail expert. Use the provided tools to check inventory and find product locations.",
            tools=[{"type": "azure_ai_search", "connection_id": "your_search_conn_id"}]
        )
        return agent