import os
from dotenv import load_dotenv

load_dotenv()

#we can carry this bit into agents module maybe
MODEL_NAME = os.getenv("MODEL_NAME", "llama3.1:8b-instruct")
MODEL_PLATFORM = os.getenv("MODEL_PLATFORM", "OLLAMA")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ollama")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
