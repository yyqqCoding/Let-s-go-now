from app.graphs.trip_graph import run_trip_graph
from app.schemas.trip import TripPlanRequest


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
