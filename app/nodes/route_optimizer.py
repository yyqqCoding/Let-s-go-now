from math import inf

from app.graphs.trip_state import TripGraphState
from app.schemas.candidates import CandidatePlace, PlaceType
from app.schemas.routes import DailyRouteGroup, RoutePlan, RouteStop


def route_optimizer(state: TripGraphState) -> dict:
    """根据已选核心地点生成按天分组的路线。

    V0.5 只做本地确定性路线分组：有经纬度时按地理位置粗排序并分天；
    没有经纬度时保留原始选择顺序。真实距离、通勤时间和地图路径会在后续 MCP 阶段接入。
    """

    request = state["request"]
    selected_places = state["selected_places"]
    sorted_attractions = _sort_by_location(selected_places.selected_attractions)
    attraction_groups = _split_evenly(sorted_attractions, request.days)

    remaining_restaurants = _sort_by_location(selected_places.selected_restaurants)
    daily_groups: list[DailyRouteGroup] = []
    route_warnings: list[str] = []

    if len(remaining_restaurants) < request.days:
        route_warnings.append(f"餐饮候选不足：当前 {len(remaining_restaurants)} 个，目标至少 {request.days} 个。")

    for day_index, attractions in enumerate(attraction_groups, start=1):
        restaurant = _pop_nearest_restaurant(attractions, remaining_restaurants)
        day_warnings: list[str] = []
        if restaurant is None:
            day_warnings.append("当天缺少可插入的餐饮候选。")

        stops = _build_daily_stops(attractions=attractions, restaurant=restaurant)
        daily_groups.append(
            DailyRouteGroup(
                day=day_index,
                area_summary=_build_area_summary(attractions),
                stops=stops,
                route_summary=_build_route_summary(day_index, stops),
                warnings=day_warnings,
            )
        )

    return {"route_plan": RoutePlan(daily_route_groups=daily_groups, warnings=route_warnings)}


def _sort_by_location(candidates: list[CandidatePlace]) -> list[CandidatePlace]:
    """按经纬度粗排序候选。

    当前不做复杂聚类；先按纬度、经度排序，让相邻坐标更容易被分到同一天。
    坐标缺失的候选放到最后，并按置信度兜底排序。
    """

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.lat is None or candidate.lng is None,
            candidate.lat if candidate.lat is not None else inf,
            candidate.lng if candidate.lng is not None else inf,
            -candidate.confidence,
        ),
    )


def _split_evenly(candidates: list[CandidatePlace], days: int) -> list[list[CandidatePlace]]:
    """把候选尽量均匀拆成 days 组。

    这里保证每天都有一个列表，即使当天没有景点，也会返回空列表，
    方便后续校验节点发现“某天缺少景点”的问题。
    """

    groups: list[list[CandidatePlace]] = []
    total = len(candidates)
    cursor = 0
    for day_offset in range(days):
        remaining_days = days - day_offset
        remaining_items = total - cursor
        group_size = (remaining_items + remaining_days - 1) // remaining_days if remaining_days else 0
        groups.append(candidates[cursor : cursor + group_size])
        cursor += group_size
    return groups


def _pop_nearest_restaurant(attractions: list[CandidatePlace], restaurants: list[CandidatePlace]) -> CandidatePlace | None:
    """为当天景点选择最近的餐饮候选。

    如果景点或餐厅缺少坐标，则退化为选择列表中的第一个餐厅，保持流程可运行。
    """

    if not restaurants:
        return None

    center = _group_center(attractions)
    if center is None:
        return restaurants.pop(0)

    best_index = min(
        range(len(restaurants)),
        key=lambda index: _distance_to_center(restaurants[index], center),
    )
    return restaurants.pop(best_index)


def _group_center(candidates: list[CandidatePlace]) -> tuple[float, float] | None:
    """计算当天景点的粗略中心点。"""

    located = [candidate for candidate in candidates if candidate.lat is not None and candidate.lng is not None]
    if not located:
        return None
    return (
        sum(candidate.lat for candidate in located if candidate.lat is not None) / len(located),
        sum(candidate.lng for candidate in located if candidate.lng is not None) / len(located),
    )


def _distance_to_center(candidate: CandidatePlace, center: tuple[float, float]) -> float:
    """计算候选到中心点的平方距离。

    不开平方可以保留距离排序结果，并减少不必要计算。
    """

    if candidate.lat is None or candidate.lng is None:
        return inf
    return (candidate.lat - center[0]) ** 2 + (candidate.lng - center[1]) ** 2


def _build_daily_stops(attractions: list[CandidatePlace], restaurant: CandidatePlace | None) -> list[RouteStop]:
    """把景点和餐饮组合成当天停靠点顺序。

    简化规则：第一个景点安排上午，餐厅插入午餐，其余景点安排下午。
    如果当天没有景点但有餐厅，餐厅仍会作为午餐停靠点保留。
    """

    stops: list[RouteStop] = []
    if attractions:
        stops.append(_to_route_stop(attractions[0], sequence=1, time_period="上午", transport_note="当天第一个地点。"))

    if restaurant is not None:
        stops.append(
            _to_route_stop(
                restaurant,
                sequence=len(stops) + 1,
                time_period="午餐",
                transport_note="插入到当天景点之间，便于减少绕路。",
            )
        )

    for attraction in attractions[1:]:
        stops.append(
            _to_route_stop(
                attraction,
                sequence=len(stops) + 1,
                time_period="下午",
                transport_note="按当前位置顺序继续游览。",
            )
        )
    return stops


def _to_route_stop(candidate: CandidatePlace, sequence: int, time_period: str, transport_note: str) -> RouteStop:
    """把 CandidatePlace 转换为 RouteStop。"""

    return RouteStop(
        sequence=sequence,
        time_period=time_period,
        place_type=candidate.type,
        name=candidate.name,
        address=candidate.address,
        lat=candidate.lat,
        lng=candidate.lng,
        estimated_cost=candidate.estimated_cost,
        estimated_duration=candidate.estimated_duration,
        transport_note=transport_note,
    )


def _build_area_summary(attractions: list[CandidatePlace]) -> str:
    """生成当天区域摘要。"""

    if not attractions:
        return "暂无景点区域"
    if all(attraction.lat is not None and attraction.lng is not None for attraction in attractions):
        return "按经纬度相近原则分组"
    return "部分地点缺少坐标，按候选顺序分组"


def _build_route_summary(day: int, stops: list[RouteStop]) -> str:
    """生成当天路线摘要。"""

    if not stops:
        return f"Day {day} 暂无可安排地点。"
    return f"Day {day}：" + " → ".join(stop.name for stop in stops)
