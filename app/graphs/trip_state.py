from typing import TypedDict

from app.schemas.trip import TripPlanRequest, TripPlanResponse


class TripGraphState(TypedDict, total=False):
    """LangGraph 节点之间共享的内部状态。

    request 是入口请求；plan 是生成后的结构化结果；error 预留给后续错误处理节点使用。
    这里使用 TypedDict，避免把图内部状态和 API Pydantic 契约耦合得过紧。
    """

    request: TripPlanRequest
    plan: TripPlanResponse
    error: str
