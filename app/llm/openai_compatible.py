import json
import re
from typing import Any

from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.core.model_config import get_openai_model_config
from app.prompts.trip_plan import TRIP_PLAN_SYSTEM_PROMPT
from app.schemas.trip import TripPlanRequest, TripPlanResponse


class OpenAICompatibleTripPlannerLLM:
    """OpenAI-compatible 旅游规划模型客户端。

    这个类只负责一件事：把已经校验过的 TripPlanRequest 交给真实模型，
    并把模型输出重新校验为 TripPlanResponse。

    不同 LangGraph 节点可以通过 node_name 读取不同模型配置。
    当前第一阶段只有 generate_plan 节点。
    """

    def __init__(self, settings: Settings, node_name: str = "generate_plan") -> None:
        self.settings = settings
        self.node_name = node_name

    def generate_plan(self, request: TripPlanRequest) -> TripPlanResponse:
        """调用真实 OpenAI-compatible 模型生成旅游计划。

        优先使用 LangChain 的 with_structured_output，让模型直接返回 Pydantic 结构。
        一些兼容接口并不完全支持结构化输出，可能返回 Markdown 包裹的 JSON，
        所以失败时会回退到普通调用，再剥离 Markdown 并做 Pydantic 校验。
        """

        model_config = get_openai_model_config(self.settings, self.node_name)
        if not model_config.api_key:
            raise ValueError(f"api_key is required in model_config.toml for node {self.node_name} when provider=openai_compatible.")

        model_kwargs = {
            "model": model_config.model,
            "api_key": model_config.api_key,
            "temperature": model_config.temperature,
        }
        if model_config.base_url:
            model_kwargs["base_url"] = model_config.base_url

        model = ChatOpenAI(**model_kwargs)
        messages = self._build_messages(request)

        try:
            structured_model = model.with_structured_output(TripPlanResponse)
            result = structured_model.invoke(messages)
            return TripPlanResponse.model_validate(result)
        except Exception:
            raw_result = model.invoke(messages)
            try:
                return TripPlanResponse.model_validate(_extract_json_payload(_get_message_content(raw_result)))
            except Exception as parse_error:
                raise ValueError("Model output does not match TripPlanResponse schema.") from parse_error

    def _build_messages(self, request: TripPlanRequest) -> list[tuple[str, str]]:
        """构造 ChatOpenAI 消息。

        system 消息保存角色和总要求；human 消息携带本次请求和响应 JSON Schema。
        """

        return [
            ("system", TRIP_PLAN_SYSTEM_PROMPT),
            ("human", self._build_user_prompt(request)),
        ]

    @staticmethod
    def _build_user_prompt(request: TripPlanRequest) -> str:
        """构造用户侧 Prompt。

        这里把 TripPlanResponse 的 JSON Schema 发给模型，减少真实模型输出字段漂移。
        """

        request_json = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, indent=2)
        schema_json = json.dumps(TripPlanResponse.model_json_schema(), ensure_ascii=False, indent=2)
        return (
            "请根据以下旅游需求生成行程计划。\n"
            "必须严格返回一个 JSON 对象，不要使用 Markdown，不要使用 ```json 代码块，不要输出额外解释。\n"
            "返回内容必须符合下面的 TripPlanResponse JSON Schema，字段名和嵌套结构必须完全一致。\n\n"
            f"旅游需求：\n{request_json}\n\n"
            f"TripPlanResponse JSON Schema：\n{schema_json}"
        )


def _get_message_content(raw_result: Any) -> str:
    """从 LangChain 返回对象中提取文本内容。"""

    content = getattr(raw_result, "content", raw_result)
    if isinstance(content, list):
        return "".join(str(item) for item in content)
    return str(content)


def _extract_json_payload(content: str) -> dict[str, Any]:
    """从模型文本中提取 JSON。

    真实兼容模型有时会返回 ```json 包裹的内容，这里只做格式剥离，
    最终结构仍交给 TripPlanResponse 做严格校验。
    """

    text = content.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced_match:
        text = fenced_match.group(1).strip()
    return json.loads(text)
