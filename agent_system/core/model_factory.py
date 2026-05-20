from camel.models import ModelFactory
from camel.types import ModelPlatformType
from camel.configs import ChatGPTConfig, AnthropicConfig
from agent_system.config import settings as config_settings
import os


def create_model(tool_choice="required"):
    platform = getattr(ModelPlatformType, config_settings.MODEL_PLATFORM)

    if platform == ModelPlatformType.ANTHROPIC:
        return ModelFactory.create(
            model_platform=platform,
            model_type=config_settings.MODEL_NAME,
            api_key=os.getenv("ANTHROPIC_API_KEY", config_settings.OPENAI_API_KEY),
            model_config_dict=AnthropicConfig(
                temperature=config_settings.TEMPERATURE,
                max_tokens=4096,
            ).as_dict(),
        )

    extra_kwargs = {}
    if platform == ModelPlatformType.OPENAI:
        org = os.getenv("OPENAI_ORG_ID") or os.getenv("OPENAI_ORGANIZATION")
        project = os.getenv("OPENAI_PROJECT") or os.getenv("OPENAI_PROJECT_ID")
        if org:
            extra_kwargs["organization"] = org
        if project:
            extra_kwargs["project"] = project

    return ModelFactory.create(
        model_platform=platform,
        model_type=config_settings.MODEL_NAME,
        url=config_settings.OPENAI_BASE_URL,
        api_key=config_settings.OPENAI_API_KEY,
        model_config_dict=ChatGPTConfig(
            temperature=config_settings.TEMPERATURE,
            stream=False,
            tool_choice=tool_choice,
        ).as_dict(),
        **extra_kwargs,
    )
