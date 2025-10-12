from camel.models import ModelFactory
from camel.types import ModelPlatformType
from camel.configs import ChatGPTConfig
from agent_system.config import settings


def create_model():
    platform = getattr(ModelPlatformType, settings.MODEL_PLATFORM)
    return ModelFactory.create(
        model_platform=platform,
        model_type=settings.MODEL_NAME,
        url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
        model_config_dict=ChatGPTConfig(temperature=settings.TEMPERATURE).as_dict(),
    )
