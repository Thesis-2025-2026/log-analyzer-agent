from camel.models import ModelFactory
from camel.types import ModelPlatformType
from camel.configs import ChatGPTConfig
from agent_system.config import settings as config_settings
import os


def create_model(tool_choice="required"):
    platform = getattr(ModelPlatformType, config_settings.MODEL_PLATFORM)
    extra_kwargs = {}
    if platform == ModelPlatformType.OPENAI:
        # Pass organization/project when present; required in some accounts
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
        # Enable streaming so CAMEL emits built-in tool call logs at INFO
        model_config_dict=ChatGPTConfig(
            temperature=config_settings.TEMPERATURE,
            stream=True,
            tool_choice=tool_choice,
        ).as_dict(),
        **extra_kwargs,
    )
