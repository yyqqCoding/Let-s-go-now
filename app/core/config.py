from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行配置。

    模型的 key、base_url、model、temperature 不放在 .env。
    它们统一放在项目根目录的 model_config.toml 中。
    这里仅保留配置文件路径，方便测试或多环境启动时切换配置文件。
    """

    model_config = SettingsConfigDict(extra="ignore")

    model_config_file: str = Field(default="model_config.toml", alias="MODEL_CONFIG_FILE")


@lru_cache
def get_settings() -> Settings:
    """缓存 Settings，避免每次请求重复解析环境变量。"""

    return Settings()
