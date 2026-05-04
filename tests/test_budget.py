from app.nodes.estimate_budget import estimate_budget
from app.schemas.trip import Activity, BudgetEstimate, DayPlan, TripPlanRequest, TripPlanResponse


def test_estimate_budget_keeps_total_and_estimated_cost_consistent_with_request_budget() -> None:
    request = TripPlanRequest(
        destination="杭州",
        days=1,
        budget=1000,
        people=2,
        preferences=["自然风景"],
        avoid=[],
        travel_style="relaxed",
    )
    plan = TripPlanResponse(
        title="杭州一日游",
        summary="轻松游览杭州。",
        destination="杭州",
        days=[
            DayPlan(
                day=1,
                theme="西湖轻松游",
                activities=[
                    Activity(
                        time_period="上午",
                        type="attraction",
                        place="西湖",
                        reason="符合自然风景偏好。",
                        estimated_cost=0,
                        tips="慢行游览。",
                    )
                ],
            )
        ],
        budget=BudgetEstimate(
            total_budget=800,
            estimated_total_cost=1200,
            currency="CNY",
            notes="模型原始估算。",
        ),
        warnings=[],
    )

    result = estimate_budget({"request": request, "plan": plan})

    assert result["plan"].budget.total_budget == 1000
    assert result["plan"].budget.estimated_total_cost == 1000
