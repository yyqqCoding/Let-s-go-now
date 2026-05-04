from app.graphs.trip_state import TripGraphState
from app.llm import get_trip_planner_llm


def build_itinerary(state: TripGraphState) -> dict:
    """生成每日行程。

    当前节点仍调用真实 OpenAI 兼容模型一次性生成完整 TripPlanResponse。
    这样可以先完成 LangGraph 节点拆分，同时保持 Swagger 返回结构和第一阶段能力不变。
    """

    request = state["request"]
    llm = get_trip_planner_llm("build_itinerary")
    return {"plan": llm.generate_plan(request)}
