from app.nodes.estimate_budget import estimate_budget
from app.schemas.hotels import HotelCandidate, HotelSelection
from app.schemas.trip import Activity, BudgetEstimate, DayPlan, TripPlanRequest, TripPlanResponse


def _request(days: int = 2, budget: float = 1500, people: int = 2, travel_style: str = "balanced") -> TripPlanRequest:
    return TripPlanRequest(
        destination="杭州",
        days=days,
        budget=budget,
        people=people,
        preferences=["自然风景", "本地美食"],
        avoid=[],
        travel_style=travel_style,
    )


def _activity(time_period: str, activity_type: str, place: str, cost: float) -> Activity:
    return Activity(
        time_period=time_period,
        type=activity_type,
        place=place,
        reason=f"{place}适合本次行程。",
        estimated_cost=cost,
        tips=f"{place}测试提示。",
    )


def _plan(days: int = 2) -> TripPlanResponse:
    return TripPlanResponse(
        title="杭州2天旅行计划",
        summary="测试预算估算。",
        destination="杭州",
        days=[
            DayPlan(
                day=1,
                theme="杭州第1天自然风景路线",
                activities=[
                    _activity("上午", "attraction", "西湖", 0),
                    _activity("午餐", "food", "知味观", 80),
                    _activity("下午", "attraction", "灵隐寺", 45),
                    _activity("晚餐", "food", "住宿区域附近晚餐", 0),
                    _activity("住宿", "hotel", "推荐住宿区域：西湖附近", 0),
                ],
            ),
            DayPlan(
                day=2,
                theme="杭州第2天本地美食路线",
                activities=[
                    _activity("上午", "attraction", "西溪湿地", 80),
                    _activity("午餐", "food", "新白鹿", 70),
                    _activity("晚餐", "food", "住宿区域附近晚餐", 0),
                    _activity("住宿", "hotel", "推荐住宿区域：西湖附近", 0),
                ],
            ),
        ][:days],
        budget=BudgetEstimate(
            total_budget=999,
            estimated_total_cost=1,
            currency="CNY",
            notes="旧预算占位。",
        ),
        warnings=[],
    )


def _selected_hotel(price_per_night: float = 420) -> HotelCandidate:
    return HotelCandidate(
        name="西湖精选酒店",
        source="hotel_research",
        area_name="西湖附近",
        address="西湖附近地址",
        lat=30.26,
        lng=120.16,
        price_per_night=price_per_night,
        rating=4.7,
        tags=["交通方便"],
        reason="靠近路线中心。",
        confidence=0.9,
        raw_evidence="测试酒店候选。",
    )


def test_budget_estimate_schema_exposes_breakdown_and_level_with_defaults() -> None:
    budget = BudgetEstimate(total_budget=1000, estimated_total_cost=800, currency="CNY", notes="测试预算。")

    assert budget.breakdown.accommodation == 0
    assert budget.breakdown.food == 0
    assert budget.breakdown.transport == 0
    assert budget.breakdown.tickets == 0
    assert budget.breakdown.other == 0
    assert budget.level == "medium"


def test_estimate_budget_builds_breakdown_from_hotel_food_transport_and_tickets() -> None:
    request = _request(days=2, budget=1500, people=2, travel_style="balanced")
    plan = _plan(days=2)

    result = estimate_budget(
        {
            "request": request,
            "plan": plan,
            "hotel_selection": HotelSelection(
                selected_hotel=_selected_hotel(price_per_night=420),
                hotel_reason="预算内且靠近路线中心。",
                backup_hotels=[],
                warnings=[],
            ),
        }
    )

    budget = result["plan"].budget
    assert budget.total_budget == 1500
    assert budget.breakdown.accommodation == 420
    assert budget.breakdown.food == 460
    assert budget.breakdown.transport == 240
    assert budget.breakdown.tickets == 250
    assert budget.breakdown.other == 0
    assert budget.estimated_total_cost == 1370
    assert budget.level == "medium"


def test_estimate_budget_changes_with_people_days_and_travel_style() -> None:
    relaxed_request = _request(days=1, budget=700, people=1, travel_style="relaxed")
    intensive_request = _request(days=2, budget=6000, people=3, travel_style="intensive")

    relaxed_budget = estimate_budget({"request": relaxed_request, "plan": _plan(days=1)})["plan"].budget
    intensive_budget = estimate_budget({"request": intensive_request, "plan": _plan(days=2)})["plan"].budget

    assert relaxed_budget.level == "medium"
    assert intensive_budget.level == "high"
    assert intensive_budget.breakdown.accommodation > relaxed_budget.breakdown.accommodation
    assert intensive_budget.breakdown.food > relaxed_budget.breakdown.food
    assert intensive_budget.breakdown.transport > relaxed_budget.breakdown.transport


def test_estimate_budget_keeps_real_estimate_and_warns_when_cost_exceeds_budget() -> None:
    request = _request(days=2, budget=500, people=2, travel_style="balanced")
    plan = _plan(days=2)

    result = estimate_budget(
        {
            "request": request,
            "plan": plan,
            "hotel_selection": HotelSelection(
                selected_hotel=_selected_hotel(price_per_night=600),
                hotel_reason="酒店偏贵。",
                backup_hotels=[],
                warnings=[],
            ),
        }
    )

    output_plan = result["plan"]
    assert output_plan.budget.total_budget == 500
    assert output_plan.budget.estimated_total_cost > 500
    assert output_plan.budget.level == "low"
    assert any("预算可能超出" in warning for warning in output_plan.warnings)
