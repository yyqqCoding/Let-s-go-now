from app.graphs.trip_state import TripGraphState
from app.llm import get_trip_planner_llm


def generate_plan(state: TripGraphState) -> dict:
    """LangGraph 的生成行程节点。

    输入 state 中必须包含经过 FastAPI/Pydantic 校验后的 request。
    节点只负责调用模型并返回 state 更新，不直接处理 HTTP 响应。
    """

    request = state["request"]
    llm = get_trip_planner_llm()
    plan = llm.generate_plan(request)
    return {"plan": plan}
