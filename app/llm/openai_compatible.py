import json
import re
from typing import Any

from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.core.model_config import get_openai_model_config
from app.prompts.trip_plan import TRIP_PLAN_SYSTEM_PROMPT
from app.schemas.candidates import CandidatePool
from app.schemas.trip import TripPlanRequest, TripPlanResponse


class OpenAICompatibleTripPlannerLLM:
    """OpenAI-compatible 旅游规划模型客户端。

    这个类只负责一件事：把已经校验过的 TripPlanRequest 交给真实模型，
    并把模型输出重新校验为 TripPlanResponse。

    不同 LangGraph 节点可以通过 node_name 读取不同模型配置。
    V0.7 后完整行程表达已改为确定性节点，当前主流程主要由 fallback_llm_research 使用该客户端生成候选池。
    """

    def __init__(self, settings: Settings, node_name: str = "build_itinerary") -> None:
        self.settings = settings
        self.node_name = node_name

    def generate_plan(self, request: TripPlanRequest) -> TripPlanResponse:
        """调用真实 OpenAI-compatible 模型生成旅游计划。

        优先使用 LangChain 的 with_structured_output，让模型直接返回 Pydantic 结构。
        一些兼容接口并不完全支持结构化输出，可能返回 Markdown 包裹的 JSON，
        所以失败时会回退到普通调用，再剥离 Markdown 并做 Pydantic 校验。
        """

        messages = self._build_messages(request)
        return self._invoke_structured_model(messages, TripPlanResponse, "Model output does not match TripPlanResponse schema.")

    def generate_candidates(self, request: TripPlanRequest) -> CandidatePool:
        """调用真实 OpenAI-compatible 模型生成候选池。

        该方法用于 V0.3 的 fallback_llm_research 节点。
        外部来源未接入前，候选景点和餐饮由真实模型生成，但仍必须符合 CandidatePool。
        """

        messages = self._build_candidate_messages(request)
        return self._invoke_structured_model(messages, CandidatePool, "Model output does not match CandidatePool schema.")

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

    def _build_candidate_messages(self, request: TripPlanRequest) -> list[tuple[str, str]]:
        """构造候选池生成消息。"""

        return [
            (
                "system",
                "你是旅游候选地点研究助手，只负责生成候选景点和餐饮地点，不生成完整行程。",
            ),
            ("human", self._build_candidate_prompt(request)),
        ]

    @staticmethod
    def _build_candidate_prompt(request: TripPlanRequest) -> str:
        """构造候选池 Prompt。

        输出必须是 CandidatePool JSON；source_status 只保留 fallback_llm_research 为 enabled。
        """

        request_json = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, indent=2)
        schema_json = json.dumps(CandidatePool.model_json_schema(), ensure_ascii=False, indent=2)
        return (
            "请根据以下旅游需求生成候选池。\n"
            "只返回一个 JSON 对象，不要使用 Markdown，不要使用 ```json 代码块，不要输出额外解释。\n"
            "候选只包含 attraction 和 food 两类；attractions 至少 4 个，foods 至少 4 个。\n"
            "所有候选的 source 必须是 fallback_llm_research。\n"
            "source_status 必须包含 source=fallback_llm_research 且 status=enabled。\n"
            "候选需要体现 preferences，并规避 avoid 中的内容。\n"
            "返回内容必须符合下面的 CandidatePool JSON Schema，字段名和嵌套结构必须完全一致。\n\n"
            f"旅游需求：\n{request_json}\n\n"
            f"CandidatePool JSON Schema：\n{schema_json}"
        )

    def _invoke_structured_model(self, messages: list[tuple[str, str]], schema: type[Any], error_message: str) -> Any:
        """调用模型并按指定 Pydantic schema 校验输出。"""

        model = self._build_model()
        try:
            structured_model = model.with_structured_output(schema)
            result = structured_model.invoke(messages)
            return schema.model_validate(result)
        except Exception:
            raw_result = model.invoke(messages)
            try:
                return schema.model_validate(_extract_json_payload(_get_message_content(raw_result)))
            except Exception as parse_error:
                raise ValueError(error_message) from parse_error

    def _build_model(self) -> ChatOpenAI:
        """根据当前节点名创建 ChatOpenAI 客户端。"""

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
        return ChatOpenAI(**model_kwargs)


def _get_message_content(raw_result: Any) -> str:
    """从 LangChain 返回对象中提取文本内容。"""

    content = getattr(raw_result, "content", raw_result)
    if isinstance(content, list):
        return "".join(str(item) for item in content)
    return str(content)


def _extract_json_payload(content: str) -> dict[str, Any]:
    """从模型文本中提取 JSON。

    真实兼容模型有时会返回 ```json 包裹的内容，这里只做格式剥离，
    最终结构仍交给调用方传入的 Pydantic schema 做严格校验。
    """

    text = content.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced_match:
        text = fenced_match.group(1).strip()
    return json.loads(text)
