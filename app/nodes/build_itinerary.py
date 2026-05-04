from app.graphs.trip_state import TripGraphState
from app.schemas.candidates import PlaceType
from app.schemas.hotels import HotelAreaPlan, HotelSelection, RecommendedHotelArea
from app.schemas.routes import DailyRouteGroup, RouteStop
from app.schemas.trip import Activity, BudgetEstimate, DayPlan, TripPlanResponse


def build_itinerary(state: TripGraphState) -> dict:
    """把已规划好的路线和住宿状态转换成每日行程。

    V0.7 之后，本节点不再调用完整规划 LLM，也不再重新选择景点、餐厅或酒店。
    上游节点已经完成候选生成、核心选点、路线排序和住宿选择；这里的职责只剩“表达”：
    把 `route_plan.daily_route_groups` 转成 API 需要的 `TripPlanResponse.days`。
    """

    request = state["request"]
    route_plan = state["route_plan"]
    hotel_area_plan = state.get("hotel_area_plan")
    hotel_selection = state.get("hotel_selection")

    days = [
        _build_day_plan(
            group=group,
            destination=request.destination,
            preferences=request.preferences,
            hotel_area_plan=hotel_area_plan,
            hotel_selection=hotel_selection,
        )
        for group in route_plan.daily_route_groups
    ]

    # route_optimizer 会尽量返回与 request.days 等长的分组；这里仍做兜底补齐，
    # 避免上游候选不足或后续改动导致 Pydantic 响应缺天。
    while len(days) < request.days:
        day_number = len(days) + 1
        days.append(
            DayPlan(
                day=day_number,
                theme=f"{request.destination} Day {day_number} 弹性安排",
                activities=[
                    _build_hotel_activity(
                        hotel_area_plan=hotel_area_plan,
                        hotel_selection=hotel_selection,
                    )
                ],
            )
        )

    warnings = _collect_warnings(state)
    estimated_total_cost = _estimate_initial_total_cost(days)

    return {
        "plan": TripPlanResponse(
            title=f"{request.destination}{request.days}天旅行计划",
            summary="本行程基于已选核心地点、路线分组和住宿状态生成，后续预算与校验节点会继续修正。",
            destination=request.destination,
            days=days[: request.days],
            budget=BudgetEstimate(
                total_budget=request.budget,
                estimated_total_cost=min(estimated_total_cost, request.budget),
                currency="CNY",
                notes="V0.7 先汇总路线活动和住宿的基础费用，V0.8 会进一步拆分住宿、餐饮、交通和门票。",
            ),
            warnings=warnings,
        )
    }


def _build_day_plan(
    group: DailyRouteGroup,
    destination: str,
    preferences: list[str],
    hotel_area_plan: HotelAreaPlan | None,
    hotel_selection: HotelSelection | None,
) -> DayPlan:
    """构造单日行程。

    每天先按 route_optimizer 给出的 stop 顺序生成景点/餐饮活动，
    再追加住宿说明。住宿说明即使没有具体酒店也会保留推荐区域，
    让最终行程具备“住哪里更合适”的信息。
    """

    primary_area = _primary_hotel_area(hotel_area_plan)
    activities = [_route_stop_to_activity(stop) for stop in group.stops]
    if not _has_dinner_activity(activities):
        activities.append(_build_dinner_guidance_activity(primary_area))
    activities.append(
        _build_hotel_activity(
            hotel_area_plan=hotel_area_plan,
            hotel_selection=hotel_selection,
        )
    )

    return DayPlan(
        day=group.day,
        theme=_build_day_theme(destination, group.day, preferences),
        activities=activities,
    )


def _route_stop_to_activity(stop: RouteStop) -> Activity:
    """把路线停靠点转换成 API 活动项。

    `RouteStop.place_type` 是内部枚举，API 的 `Activity.type` 当前是字符串。
    这里保持 `attraction` / `food` 两类输出，后续前端或校验节点可以稳定识别。
    """

    return Activity(
        time_period=stop.time_period,
        type=_activity_type_from_place_type(stop.place_type),
        place=stop.name,
        reason=stop.transport_note,
        estimated_cost=stop.estimated_cost,
        tips=f"地址：{stop.address}；预计停留 {stop.estimated_duration} 分钟。",
    )


def _activity_type_from_place_type(place_type: PlaceType) -> str:
    """转换地点类型为行程活动类型。"""

    if place_type == PlaceType.FOOD:
        return "food"
    return "attraction"


def _build_hotel_activity(
    hotel_area_plan: HotelAreaPlan | None,
    hotel_selection: HotelSelection | None,
) -> Activity:
    """构造每日住宿说明活动。

    有具体酒店时使用 `selected_hotel`；没有具体酒店时使用推荐住宿区域。
    这符合当前阶段“不编造酒店”的约束，同时让 Swagger 输出能看到住宿安排依据。
    """

    selected_hotel = hotel_selection.selected_hotel if hotel_selection else None
    if selected_hotel is not None:
        return Activity(
            time_period="住宿",
            type="hotel",
            place=selected_hotel.name,
            reason=hotel_selection.hotel_reason if hotel_selection else selected_hotel.reason,
            estimated_cost=selected_hotel.price_per_night,
            tips=f"区域：{selected_hotel.area_name}；地址：{selected_hotel.address}；评分 {selected_hotel.rating}。",
        )

    primary_area = _primary_hotel_area(hotel_area_plan)
    area_name = primary_area.name if primary_area else "目的地中心区域"
    area_reason = primary_area.reason if primary_area else "暂未获得具体酒店候选，先保留住宿区域建议。"
    hotel_reason = hotel_selection.hotel_reason if hotel_selection else area_reason
    return Activity(
        time_period="住宿",
        type="hotel",
        place=f"推荐住宿区域：{area_name}",
        reason=hotel_reason,
        estimated_cost=0,
        tips=f"建议优先选择{area_name}附近住宿；当前未接入酒店数据，暂不指定具体酒店。{area_reason}",
    )


def _build_day_theme(destination: str, day: int, preferences: list[str]) -> str:
    """生成面向用户的每日主题。

    `DailyRouteGroup.area_summary` 可能包含“缺少坐标”等内部诊断信息，
    不适合直接展示给用户。这里改用目的地、天数和用户偏好生成稳定主题。
    """

    preference_text = _build_preference_theme_text(preferences)
    if preference_text:
        return f"{destination}第{day}天{preference_text}路线"
    return f"{destination}第{day}天精选路线"


def _build_preference_theme_text(preferences: list[str]) -> str:
    """把用户偏好压缩成适合标题展示的短文本。"""

    cleaned_preferences = [_clean_preference(preference) for preference in preferences]
    visible_preferences = [preference for preference in cleaned_preferences if preference]
    return "与".join(visible_preferences[:2])


def _clean_preference(preference: str) -> str:
    """清理偏好中的口语化前缀，让标题更自然。"""

    return preference.removeprefix("喜欢").strip()


def _has_dinner_activity(activities: list[Activity]) -> bool:
    """判断当天是否已有晚餐安排。"""

    return any(activity.time_period == "晚餐" for activity in activities)


def _build_dinner_guidance_activity(primary_area: RecommendedHotelArea | None) -> Activity:
    """在路线没有晚餐时追加一个轻量晚餐建议。

    当前餐厅选择阶段只保证每天至少一个餐饮点，通常作为午餐插入。
    为了让 V0.7 输出满足“晚餐安排”的基本结构，这里补充住宿区域附近晚餐建议，
    但不编造具体餐厅名称。
    """

    area_name = primary_area.name if primary_area else "住宿区域"
    return Activity(
        time_period="晚餐",
        type="food",
        place="住宿区域附近晚餐",
        reason=f"当天路线未选出晚餐餐厅，建议回到{area_name}附近就餐，减少夜间通勤。",
        estimated_cost=0,
        tips="当前未接入晚餐候选数据，建议优先选择步行可达、排队较少的本地餐厅。",
    )


def _primary_hotel_area(hotel_area_plan: HotelAreaPlan | None) -> RecommendedHotelArea | None:
    """获取优先级最高的推荐住宿区域。"""

    if hotel_area_plan is None or not hotel_area_plan.recommended_hotel_areas:
        return None
    return sorted(hotel_area_plan.recommended_hotel_areas, key=lambda area: area.priority)[0]


def _collect_warnings(state: TripGraphState) -> list[str]:
    """汇总上游路线和住宿节点产生的 warning。

    V0.7 先把重要风险提示带入最终响应；V0.8 的 verify_plan 会进一步拆分 errors / warnings。
    """

    warnings: list[str] = []
    route_plan = state.get("route_plan")
    if route_plan is not None:
        warnings.extend(route_plan.warnings)
        for group in route_plan.daily_route_groups:
            warnings.extend(group.warnings)

    hotel_area_plan = state.get("hotel_area_plan")
    if hotel_area_plan is not None:
        warnings.extend(hotel_area_plan.warnings)
        for area in hotel_area_plan.recommended_hotel_areas:
            warnings.extend(area.warnings)

    hotel_candidates = state.get("hotel_candidates")
    if hotel_candidates is not None:
        warnings.extend(hotel_candidates.warnings)

    hotel_selection = state.get("hotel_selection")
    if hotel_selection is not None:
        warnings.extend(hotel_selection.warnings)

    return _deduplicate_warnings(warnings)


def _deduplicate_warnings(warnings: list[str]) -> list[str]:
    """按出现顺序去重 warning，避免最终响应重复刷屏。"""

    deduped: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning and warning not in seen:
            deduped.append(warning)
            seen.add(warning)
    return deduped


def _estimate_initial_total_cost(days: list[DayPlan]) -> float:
    """汇总行程活动的基础费用。

    这里不是最终预算模型，只给 `TripPlanResponse` 一个可校验的初始估算；
    后续 `estimate_budget` 节点仍会把总预算校正为用户输入，并在 V0.8 做规则化预算拆分。
    """

    return sum(activity.estimated_cost for day in days for activity in day.activities)
