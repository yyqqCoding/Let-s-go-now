from typing import Any, TypedDict

from app.schemas.candidates import CandidatePool
from app.schemas.selection import SelectedPlaces
from app.schemas.trip import TripPlanRequest, TripPlanResponse


class TripGraphState(TypedDict, total=False):
    """LangGraph 节点之间共享的内部状态。

    request 是入口请求；plan 是生成后的结构化结果；error 预留给后续错误处理节点使用。
    V0.2 开始增加 intent、candidates、verification 等中间字段，让后续节点能逐步替换实现。
    V0.3 后 candidates 固定为 CandidatePool，后续选点节点直接消费该结构。
    V0.4 后 selected_places 固定为 SelectedPlaces，后续路线优化节点直接消费该结构。
    这里使用 TypedDict，避免把图内部状态和 API Pydantic 契约耦合得过紧。
    """

    request: TripPlanRequest
    intent: dict[str, Any]
    candidates: CandidatePool
    selected_places: SelectedPlaces
    plan: TripPlanResponse
    verification: dict[str, Any]
    error: str
