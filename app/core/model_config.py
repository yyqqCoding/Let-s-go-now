from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
import tomllib

from app.core.config import Settings

# 第一阶段结束后，项目只保留真实模型路径。
# provider 只允许 openai_compatible，所有节点都通过 OpenAI 兼容接口调用真实模型。
LLMProvider = Literal["openai_compatible"]


@dataclass(frozen=True)
class OpenAIModelConfig:
    """单个 LangGraph 节点实际使用的模型配置。

    node_name 用于标识节点，例如 generate_plan。
    model/api_key/base_url/temperature 来自根目录 model_config.toml。
    节点专属配置为空时，会回退到 openai.default。
    """

    node_name: str
    model: str
    api_key: str | None
    base_url: str | None
    temperature: float


def get_llm_provider(settings: Settings) -> LLMProvider:
    """读取全局 LLM provider。

    当前只支持 openai_compatible。保留 provider 字段是为了让配置文件语义清晰，
    也方便后续如果接入其它真实兼容协议时做显式扩展。
    """

    config = _load_model_config(settings)
    provider = str(config.get("llm", {}).get("provider", "openai_compatible"))
    if provider != "openai_compatible":
        raise ValueError(f"Unsupported LLM provider in {settings.model_config_file}: {provider}")
    return "openai_compatible"


def get_openai_model_config(settings: Settings, node_name: str) -> OpenAIModelConfig:
    """按节点读取 OpenAI-compatible 模型配置。

    配置优先级：openai.nodes.<node_name> > openai.default。
    这样后续新增节点时，可以让不同节点使用不同模型、不同地址或不同温度。
    """

    config = _load_model_config(settings)
    openai_config = config.get("openai", {})
    default_config = openai_config.get("default", {})
    # 节点配置是可选项：没有单独配置时直接使用 default。
    # 这样新增 LangGraph 节点不需要立刻修改 model_config.toml。
    node_config = openai_config.get("nodes", {}).get(node_name) or {}

    return OpenAIModelConfig(
        node_name=node_name,
        model=str(_first_non_empty(node_config.get("model"), default_config.get("model"), "gpt-4o-mini")),
        api_key=_optional_string(_first_non_empty(node_config.get("api_key"), default_config.get("api_key"))),
        base_url=_optional_string(_first_non_empty(node_config.get("base_url"), default_config.get("base_url"))),
        temperature=float(_first_non_empty(node_config.get("temperature"), default_config.get("temperature"), 0)),
    )


def _load_model_config(settings: Settings) -> dict[str, Any]:
    """加载根目录模型配置文件。

    默认文件是 model_config.toml，也可以通过 MODEL_CONFIG_FILE 指向其它配置文件，
    主要用于测试或多环境启动。
    """

    path = Path(settings.model_config_file)
    if not path.exists():
        raise FileNotFoundError(f"Model config file not found: {settings.model_config_file}")
    with path.open("rb") as file:
        return tomllib.load(file)


def _first_non_empty(*values: object) -> object:
    """返回第一个非 None、非空字符串的配置值。"""

    for value in values:
        if value is not None and value != "":
            return value
    return None


def _optional_string(value: object) -> str | None:
    """把 TOML 中的可选字符串统一转换为 str | None。"""

    if value is None or value == "":
        return None
    return str(value)
