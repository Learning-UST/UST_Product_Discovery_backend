"""
AutoGen Agent Configuration
Configures Azure OpenAI for AutoGen agents
"""
 
from utils.logger import get_logger
from typing import Dict, Any, List
from utils.config import get_config_value


logger = get_logger()
 
def get_llm_config() -> List[Dict[str, Any]]:
    """
    Get LLM configuration for AutoGen agents using Azure OpenAI.
   
    Returns:
        LLM configuration dictionary for AutoGen
    """
    config = [
        {
            "model": get_config_value("AZURE_OPENAI_DEPLOYMENT"),
            "api_type": "azure",
            "api_key": get_config_value("AZURE_OPENAI_API_KEY"),
            "base_url": get_config_value("AZURE_OPENAI_ENDPOINT"),
            "api_version": get_config_value("AZURE_OPENAI_API_VERSION"),
            "temperature": get_config_value("AGENT_TEMPERATURE"),
            "max_tokens": get_config_value("AGENT_MAX_TOKENS"),
            "timeout": get_config_value("AGENT_TIMEOUT")
        }
    ]
   
    logger.debug("LLM configuration prepared for AutoGen agents")
    return config
 
 
def get_agent_config(agent_name: str, system_message: str) -> Dict[str, Any]:
    """
    Get configuration for a specific agent.
   
    Args:
        agent_name: Name of the agent
        system_message: System prompt for the agent
       
    Returns:
        Agent configuration dictionary
    """
    return {
        "name": agent_name,
        "system_message": system_message,
        "llm_config": {
            "config_list": get_llm_config(),
            "cache_seed": None  # Disable caching for production
        },
        "human_input_mode": "NEVER",  # Fully autonomous
        "max_consecutive_auto_reply": 10,
        "code_execution_config": False  # Disable code execution for security
    }
 