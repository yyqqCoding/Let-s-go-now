from app.graphs.trip_graph import build_trip_graph, run_trip_graph
from app.schemas.trip import TripPlanRequest


def test_trip_graph_contains_v02_nodes() -> None:
    graph = build_trip_graph()

    graph_data = graph.get_graph()
    node_names = set(graph_data.nodes)

    assert "parse_intent" in node_names
    assert "generate_candidates" in node_names
    assert "build_itinerary" in node_names
    assert "estimate_budget" in node_names
    assert "verify_plan" in node_names
    assert "final_output" in node_names


def test_trip_graph_generates_plan() -> None:
    request = TripPlanRequest(
        destination="成都",
        days=2,
        budget=800,
        people=1,
        preferences=["美食", "城市漫步"],
        avoid=["高消费"],
        travel_style="balanced",
    )

    plan = run_trip_graph(request)

    assert plan.destination == "成都"
    assert len(plan.days) == 2
    assert plan.budget.total_budget == 800
