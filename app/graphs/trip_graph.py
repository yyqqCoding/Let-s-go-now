from langgraph.graph import END, START, StateGraph

from app.graphs.trip_state import TripGraphState
from app.nodes import (
    build_itinerary,
    estimate_budget,
    final_output,
    generate_candidates,
    hotel_area_selector,
    hotel_research,
    hotel_selector,
    parse_intent,
    route_optimizer,
    select_core_places,
    verify_plan,
)
from app.schemas.trip import TripPlanRequest, TripPlanResponse


def build_trip_graph():
    """构建旅游规划 LangGraph。

    V0.2 把原来的单节点生成拆成多个清晰步骤。
    当前仍由 build_itinerary 调用真实模型生成完整行程；
    V0.6 已在生成行程前得到基于路线反推的住宿区域建议，并保留酒店候选与选择状态。
    """

    builder = StateGraph(TripGraphState)
    builder.add_node("parse_intent", parse_intent)
    builder.add_node("generate_candidates", generate_candidates)
    builder.add_node("select_core_places", select_core_places)
    builder.add_node("route_optimizer", route_optimizer)
    builder.add_node("hotel_area_selector", hotel_area_selector)
    builder.add_node("hotel_research", hotel_research)
    builder.add_node("hotel_selector", hotel_selector)
    builder.add_node("build_itinerary", build_itinerary)
    builder.add_node("estimate_budget", estimate_budget)
    builder.add_node("verify_plan", verify_plan)
    builder.add_node("final_output", final_output)

    builder.add_edge(START, "parse_intent")
    builder.add_edge("parse_intent", "generate_candidates")
    builder.add_edge("generate_candidates", "select_core_places")
    builder.add_edge("select_core_places", "route_optimizer")
    builder.add_edge("route_optimizer", "hotel_area_selector")
    builder.add_edge("hotel_area_selector", "hotel_research")
    builder.add_edge("hotel_research", "hotel_selector")
    builder.add_edge("hotel_selector", "build_itinerary")
    builder.add_edge("build_itinerary", "estimate_budget")
    builder.add_edge("estimate_budget", "verify_plan")
    builder.add_edge("verify_plan", "final_output")
    builder.add_edge("final_output", END)
    return builder.compile()


trip_graph = build_trip_graph()


def run_trip_graph(request: TripPlanRequest) -> TripPlanResponse:
    """运行旅游规划图，并把最终结果校验为 TripPlanResponse。"""

    result = trip_graph.invoke({"request": request})
    plan = result["plan"]
    return TripPlanResponse.model_validate(plan)
