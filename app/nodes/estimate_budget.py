from math import ceil

from app.graphs.trip_state import TripGraphState
from app.schemas.hotels import HotelSelection
from app.schemas.trip import Activity, BudgetBreakdown, BudgetEstimate, BudgetLevel, DayPlan, TravelStyle


def estimate_budget(state: TripGraphState) -> dict:
    """按规则估算旅行预算。

    V0.8.1 后，本节点不再只是把预算字段截断为用户输入，而是根据行程活动、
    人数、天数、旅行节奏和酒店选择拆分住宿、餐饮、交通、门票等费用。
    真实估算可能高于用户预算；这种情况会保留估算值并追加 warning，供后续 verify_plan 判断。
    """

    request = state["request"]
    plan = state["plan"].model_copy(deep=True)
    budget_level = _classify_budget_level(total_budget=request.budget, people=request.people, days=request.days)
    hotel_selection = state.get("hotel_selection")

    breakdown = BudgetBreakdown(
        accommodation=_estimate_accommodation_cost(
            request_budget=request.budget,
            people=request.people,
            days=request.days,
            budget_level=budget_level,
            hotel_selection=hotel_selection,
        ),
        food=_estimate_food_cost(plan.days, request.people, budget_level),
        transport=_estimate_transport_cost(request.days, request.people, request.travel_style),
        tickets=_estimate_ticket_cost(plan.days, request.people),
        other=0,
    )
    estimated_total_cost = _sum_breakdown(breakdown)
    warnings = list(plan.warnings)

    if estimated_total_cost > request.budget:
        warnings.append(
            f"预算可能超出：规则估算约 {estimated_total_cost:.0f} 元，高于总预算 {request.budget:.0f} 元。"
        )

    plan.budget = BudgetEstimate(
        total_budget=request.budget,
        estimated_total_cost=estimated_total_cost,
        currency=plan.budget.currency,
        notes=_build_budget_notes(budget_level),
        breakdown=breakdown,
        level=budget_level,
    )
    plan.warnings = _deduplicate_warnings(warnings)
    return {"plan": plan}


def _classify_budget_level(total_budget: float, people: int, days: int) -> BudgetLevel:
    """按人均每天预算判断预算等级。

    该等级不是消费建议，只是估算参数。阈值保持简单可解释：
    低预算 < 300 元/人/天，高预算 >= 800 元/人/天，其余为中等预算。
    """

    budget_per_person_day = total_budget / max(people, 1) / max(days, 1)
    if budget_per_person_day < 300:
        return BudgetLevel.LOW
    if budget_per_person_day >= 800:
        return BudgetLevel.HIGH
    return BudgetLevel.MEDIUM


def _estimate_accommodation_cost(
    request_budget: float,
    people: int,
    days: int,
    budget_level: BudgetLevel,
    hotel_selection: HotelSelection | None,
) -> float:
    """估算住宿费用。

    有具体酒店时使用酒店每晚价格；没有具体酒店时按预算等级兜底。
    兜底价格随预算等级变化，保证预算会随人数、天数和预算水平合理变化。
    """

    nights = max(days - 1, 1)
    room_count = max(ceil(people / 2), 1)
    selected_hotel = hotel_selection.selected_hotel if hotel_selection else None
    if selected_hotel is not None:
        return selected_hotel.price_per_night * nights * room_count

    fallback_price_per_room = {
        BudgetLevel.LOW: 220,
        BudgetLevel.MEDIUM: 420,
        BudgetLevel.HIGH: 760,
    }[budget_level]
    # 当总预算极低时，兜底价格不能完全吞掉预算；这里给低预算保留一定餐饮和交通空间。
    if budget_level == BudgetLevel.LOW:
        fallback_price_per_room = min(fallback_price_per_room, request_budget * 0.35 / nights / room_count)
    return round(fallback_price_per_room * nights * room_count, 2)


def _estimate_food_cost(days: list[DayPlan], people: int, budget_level: BudgetLevel) -> float:
    """估算餐饮费用。

    具体餐厅费用通常是单人费用，按人数放大。V0.7 追加的晚餐兜底活动费用为 0，
    这里按预算等级补一个默认餐标，避免总预算低估。
    """

    fallback_meal_cost = {
        BudgetLevel.LOW: 40,
        BudgetLevel.MEDIUM: 40,
        BudgetLevel.HIGH: 120,
    }[budget_level]
    total = 0.0
    for day in days:
        for activity in _activities_by_type(day, "food"):
            meal_cost = activity.estimated_cost if activity.estimated_cost > 0 else fallback_meal_cost
            total += meal_cost * people
    return total


def _estimate_transport_cost(days: int, people: int, travel_style: TravelStyle) -> float:
    """估算市内交通费用。

    当前还没有地图通勤时间，先按旅行节奏给每人每天交通预算：
    relaxed 少移动，intensive 移动更多。
    """

    daily_cost = {
        TravelStyle.RELAXED: 40,
        TravelStyle.BALANCED: 60,
        TravelStyle.INTENSIVE: 80,
    }[travel_style]
    return daily_cost * days * people


def _estimate_ticket_cost(days: list[DayPlan], people: int) -> float:
    """估算门票费用。

    景点活动费用按单人门票理解，因此需要乘以人数。
    免费景点保留 0 元。
    """

    return sum(activity.estimated_cost * people for day in days for activity in _activities_by_type(day, "attraction"))


def _activities_by_type(day: DayPlan, activity_type: str) -> list[Activity]:
    """按活动类型筛选单日活动。"""

    return [activity for activity in day.activities if activity.type == activity_type]


def _sum_breakdown(breakdown: BudgetBreakdown) -> float:
    """汇总预算拆分。"""

    return (
        breakdown.accommodation
        + breakdown.food
        + breakdown.transport
        + breakdown.tickets
        + breakdown.other
    )


def _build_budget_notes(budget_level: BudgetLevel) -> str:
    """生成预算说明。"""

    level_text = {
        BudgetLevel.LOW: "低预算",
        BudgetLevel.MEDIUM: "中等预算",
        BudgetLevel.HIGH: "高预算",
    }[budget_level]
    return f"按{level_text}规则估算，已拆分住宿、餐饮、交通、门票和其它费用。"


def _deduplicate_warnings(warnings: list[str]) -> list[str]:
    """按出现顺序去重 warning。"""

    deduped: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning and warning not in seen:
            deduped.append(warning)
            seen.add(warning)
    return deduped
