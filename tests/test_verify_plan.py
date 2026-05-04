from app.nodes.final_output import final_output
from app.nodes.verify_plan import verify_plan
from app.schemas.trip import Activity, BudgetBreakdown, BudgetEstimate, DayPlan, TripPlanRequest, TripPlanResponse


def _request(days: int = 1, budget: float = 1000, travel_style: str = "relaxed") -> TripPlanRequest:
    return TripPlanRequest(
        destination="杭州",
        days=days,
        budget=budget,
        people=2,
        preferences=["自然风景", "本地美食"],
        avoid=["购物"],
        travel_style=travel_style,
    )


def _activity(time_period: str, activity_type: str, place: str, cost: float = 0) -> Activity:
    return Activity(
        time_period=time_period,
        type=activity_type,
        place=place,
        reason=f"{place}适合本次旅行。",
        estimated_cost=cost,
        tips=f"{place}游玩提示。",
    )


def _plan(
    activities: list[Activity] | None = None,
    total_budget: float = 1000,
    estimated_total_cost: float = 800,
    warnings: list[str] | None = None,
) -> TripPlanResponse:
    return TripPlanResponse(
        title="杭州1天旅行计划",
        summary="测试行程校验。",
        destination="杭州",
        days=[
            DayPlan(
                day=1,
                theme="杭州第1天自然风景与本地美食路线",
                activities=activities
                or [
                    _activity("上午", "attraction", "西湖", 0),
                    _activity("午餐", "food", "知味观", 80),
                    _activity("晚餐", "food", "住宿区域附近晚餐", 0),
                    _activity("住宿", "hotel", "推荐住宿区域：西湖附近", 0),
                ],
            )
        ],
        budget=BudgetEstimate(
            total_budget=total_budget,
            estimated_total_cost=estimated_total_cost,
            currency="CNY",
            notes="测试预算。",
            breakdown=BudgetBreakdown(accommodation=300, food=200, transport=100, tickets=200, other=0),
            level="medium",
        ),
        warnings=warnings or [],
    )


def test_verify_plan_marks_complete_plan_valid() -> None:
    result = verify_plan({"request": _request(), "plan": _plan()})

    verification = result["verification"]
    assert verification["is_valid"] is True
    assert verification["errors"] == []
    assert verification["warnings"] == []


def test_verify_plan_records_errors_when_day_lacks_food_or_hotel() -> None:
    plan = _plan(
        activities=[
            _activity("上午", "attraction", "西湖", 0),
            _activity("下午", "attraction", "灵隐寺", 45),
        ]
    )

    result = verify_plan({"request": _request(), "plan": plan})

    verification = result["verification"]
    assert verification["is_valid"] is False
    assert any("第1天缺少餐饮安排" in error for error in verification["errors"])
    assert any("第1天缺少住宿安排" in error for error in verification["errors"])


def test_verify_plan_warns_when_budget_exceeds_request_budget() -> None:
    result = verify_plan({"request": _request(budget=500), "plan": _plan(total_budget=500, estimated_total_cost=680)})

    verification = result["verification"]
    assert verification["is_valid"] is True
    assert any("预算估算超出" in warning for warning in verification["warnings"])


def test_verify_plan_does_not_duplicate_existing_budget_warning() -> None:
    plan = _plan(
        total_budget=500,
        estimated_total_cost=680,
        warnings=["预算可能超出：规则估算约 680 元，高于总预算 500 元。"],
    )

    result = verify_plan({"request": _request(budget=500), "plan": plan})

    budget_warnings = [
        warning
        for warning in result["verification"]["warnings"]
        if "预算可能超出" in warning or "预算估算超出" in warning
    ]
    assert budget_warnings == ["预算可能超出：规则估算约 680 元，高于总预算 500 元。"]


def test_verify_plan_warns_when_avoid_text_appears_in_plan() -> None:
    plan = _plan(
        activities=[
            _activity("上午", "attraction", "购物街", 0),
            _activity("午餐", "food", "知味观", 80),
            _activity("住宿", "hotel", "推荐住宿区域：西湖附近", 0),
        ]
    )

    result = verify_plan({"request": _request(), "plan": plan})

    assert any("命中规避项" in warning for warning in result["verification"]["warnings"])


def test_verify_plan_warns_when_relaxed_trip_is_too_crowded() -> None:
    plan = _plan(
        activities=[
            _activity("上午", "attraction", "西湖", 0),
            _activity("上午", "attraction", "灵隐寺", 45),
            _activity("下午", "attraction", "西溪湿地", 80),
            _activity("下午", "attraction", "宋城", 300),
            _activity("午餐", "food", "知味观", 80),
            _activity("晚餐", "food", "住宿区域附近晚餐", 0),
            _activity("住宿", "hotel", "推荐住宿区域：西湖附近", 0),
        ]
    )

    result = verify_plan({"request": _request(travel_style="relaxed"), "plan": plan})

    assert any("行程偏满" in warning for warning in result["verification"]["warnings"])


def test_final_output_merges_verification_errors_and_warnings() -> None:
    plan = _plan(warnings=["原始 warning"])

    result = final_output(
        {
            "plan": plan,
            "verification": {
                "is_valid": False,
                "errors": ["缺少餐饮安排"],
                "warnings": ["预算估算超出"],
            },
        }
    )

    output_warnings = result["plan"].warnings
    assert output_warnings == ["原始 warning", "缺少餐饮安排", "预算估算超出"]
