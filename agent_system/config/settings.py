import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure verbose logging for camel-ai
def configure_logging():
    """Configure logging for the application and camel-ai."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Set up logging format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_format,
        datefmt=date_format,
        force=True,  # Override any existing configuration
    )
    
    # Enable verbose logging for camel-ai specifically
    camel_logger = logging.getLogger("camel")
    camel_logger.setLevel(logging.DEBUG)
    
    # Also enable DEBUG for camel submodules
    logging.getLogger("camel.agents").setLevel(logging.DEBUG)
    logging.getLogger("camel.models").setLevel(logging.DEBUG)
    logging.getLogger("camel.societies").setLevel(logging.DEBUG)
    logging.getLogger("camel.tasks").setLevel(logging.DEBUG)
    logging.getLogger("camel.retrievers").setLevel(logging.DEBUG)
    logging.getLogger("camel.embeddings").setLevel(logging.DEBUG)
    logging.getLogger("camel.storages").setLevel(logging.DEBUG)

# Initialize logging configuration
configure_logging()

# OpenAI model configuration
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.1-2025-11-13")
MODEL_PLATFORM = os.getenv("MODEL_PLATFORM", "OPENAI")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is required in .env file")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
