from app.graphs.trip_state import TripGraphState
from app.schemas.hotels import HotelAreaPlan, RecommendedHotelArea
from app.schemas.routes import DailyRouteGroup, RouteStop

# 使用经纬度平方距离做粗略跨度判断。
# 这里不是精确公里数，只用于识别“迪士尼和市中心”这类明显跨区路线。
_LARGE_ROUTE_SPAN_THRESHOLD = 0.018


def hotel_area_selector(state: TripGraphState) -> dict:
    """根据已规划路线反推推荐住宿区域。

    V0.6 的职责边界很窄：只消费 `route_plan.daily_route_groups` 和用户请求，
    输出 `hotel_area_plan.recommended_hotel_areas`。当前不调用 LLM、不搜索酒店、
    不生成具体酒店候选，避免把后续 `hotel_research` / `hotel_selector` 的职责提前合并进来。
    """

    request = state["request"]
    route_plan = state["route_plan"]
    daily_groups = route_plan.daily_route_groups

    located_stops = _collect_located_stops(daily_groups)
    overall_center = _center_of_stops(located_stops)
    related_days = [group.day for group in daily_groups]
    warnings: list[str] = []
    area_warnings: list[str] = []

    if not daily_groups:
        warnings.append("当前没有可用的每日路线，住宿区域只能按目的地兜底推荐。")

    if not located_stops:
        warnings.append("路线停靠点缺少经纬度，住宿区域暂按目的地中心区域兜底。")
        area_warnings.append("缺少路线坐标，后续接入地图能力后需要重新校正住宿区域。")

    if _route_span_is_large(located_stops):
        span_warning = "路线跨度较大，可考虑在远距离路线当天换酒店，减少往返通勤。"
        warnings.append(span_warning)
        area_warnings.append(span_warning)

    primary_area = RecommendedHotelArea(
        name=_build_area_name(request.destination, request.days, daily_groups),
        priority=1,
        center_lat=_round_coordinate(overall_center[0]) if overall_center else None,
        center_lng=_round_coordinate(overall_center[1]) if overall_center else None,
        reason=_build_reason(request.days, located_stops),
        suitable_for=_build_suitable_for(request.days),
        related_days=related_days,
        warnings=area_warnings,
    )

    return {
        "hotel_area_plan": HotelAreaPlan(
            recommended_hotel_areas=[primary_area],
            strategy_summary=_build_strategy_summary(request.destination, request.days, bool(located_stops)),
            warnings=warnings,
        )
    }


def _collect_located_stops(daily_groups: list[DailyRouteGroup]) -> list[RouteStop]:
    """收集带经纬度的路线停靠点。

    酒店区域选择依赖路线空间分布；没有坐标的点不能参与中心点和跨度计算，
    但不会中断流程，避免外部地图能力未接入时影响主链路。
    """

    return [
        stop
        for group in daily_groups
        for stop in group.stops
        if stop.lat is not None and stop.lng is not None
    ]


def _center_of_stops(stops: list[RouteStop]) -> tuple[float, float] | None:
    """计算所有路线停靠点的粗略中心。

    当前使用简单平均值，目的是给后续酒店搜索提供稳定起点；
    等接入地图或商圈数据后，可替换为交通时间加权中心。
    """

    if not stops:
        return None
    return (
        sum(stop.lat for stop in stops if stop.lat is not None) / len(stops),
        sum(stop.lng for stop in stops if stop.lng is not None) / len(stops),
    )


def _route_span_is_large(stops: list[RouteStop]) -> bool:
    """判断路线分布是否明显跨区。

    使用纬度跨度平方加经度跨度平方，避免依赖第三方地理库。
    该判断只产生提示，不改变主推荐区域，后续酒店选择阶段再决定是否真的换酒店。
    """

    if len(stops) < 2:
        return False

    lats = [stop.lat for stop in stops if stop.lat is not None]
    lngs = [stop.lng for stop in stops if stop.lng is not None]
    if not lats or not lngs:
        return False

    span_score = (max(lats) - min(lats)) ** 2 + (max(lngs) - min(lngs)) ** 2
    return span_score >= _LARGE_ROUTE_SPAN_THRESHOLD


def _build_area_name(destination: str, days: int, daily_groups: list[DailyRouteGroup]) -> str:
    """生成住宿区域名称。

    名称刻意保持语义化，而不是伪造具体商圈；后续真实 POI 或酒店源接入后，
    再把该区域转成可搜索的商圈、地铁站或行政区。
    """

    if days == 1 and daily_groups:
        return f"{daily_groups[0].area_summary}起终点区域"
    if days == 2:
        return f"{destination}路线中心区域"
    return f"{destination}主要景点分布重心区域"


def _build_reason(days: int, located_stops: list[RouteStop]) -> str:
    """根据行程天数生成推荐理由。"""

    coordinate_note = "已参考路线停靠点坐标" if located_stops else "当前缺少路线坐标，先按目的地中心"
    if days == 1:
        return f"{coordinate_note}，建议靠近当天路线起点或终点，减少抵达和返程时间。"
    if days == 2:
        return f"{coordinate_note}，建议靠近两天路线中心区域，减少每天出发和返回酒店的通勤。"
    return f"{coordinate_note}，建议靠近主要景点分布重心，并关注远距离路线当天是否需要换酒店。"


def _build_suitable_for(days: int) -> str:
    """描述推荐区域适合的住宿策略。"""

    if days == 1:
        return "一日行程优先选择起终点附近，方便抵达和离开。"
    if days == 2:
        return "两日行程优先选择单一中心区域，减少频繁换酒店成本。"
    return "多日行程优先选择主要景点重心区域，远距离单日路线可作为换酒店备选。"


def _build_strategy_summary(destination: str, days: int, has_coordinates: bool) -> str:
    """生成整体住宿策略摘要，方便接口验收和日志排查。"""

    coordinate_basis = "路线坐标" if has_coordinates else "目的地兜底信息"
    if days == 1:
        return f"{destination} {days} 天行程：基于{coordinate_basis}，优先住在当天路线起点或终点附近。"
    if days == 2:
        return f"{destination} {days} 天行程：基于{coordinate_basis}，优先住在两天路线中心区域。"
    return f"{destination} {days} 天行程：基于{coordinate_basis}，优先住在主要景点分布重心区域。"


def _round_coordinate(value: float) -> float:
    """统一经纬度精度，避免接口返回过多无意义小数。"""

    return round(value, 3)
