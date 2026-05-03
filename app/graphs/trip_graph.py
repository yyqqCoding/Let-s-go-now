from langgraph.graph import END, START, StateGraph

from app.graphs.trip_state import TripGraphState
from app.nodes.generate_plan import generate_plan
from app.schemas.trip import TripPlanRequest, TripPlanResponse


def build_trip_graph():
    """构建旅游规划 LangGraph。

    第一阶段只有一个节点：generate_plan。
    后续新增节点时，只需要在这里注册节点并调整边关系。
    """

    builder = StateGraph(TripGraphState)
    builder.add_node("generate_plan", generate_plan)
    builder.add_edge(START, "generate_plan")
    builder.add_edge("generate_plan", END)
    return builder.compile()


trip_graph = build_trip_graph()


def run_trip_graph(request: TripPlanRequest) -> TripPlanResponse:
    """运行旅游规划图，并把最终结果校验为 TripPlanResponse。"""

    result = trip_graph.invoke({"request": request})
    plan = result["plan"]
    return TripPlanResponse.model_validate(plan)
