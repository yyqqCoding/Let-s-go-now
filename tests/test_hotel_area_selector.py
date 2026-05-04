from app.graphs.trip_state import TripGraphState
from app.nodes.hotel_area_selector import hotel_area_selector
from app.schemas.candidates import PlaceType
from app.schemas.hotels import HotelAreaPlan, RecommendedHotelArea
from app.schemas.routes import DailyRouteGroup, RoutePlan, RouteStop
from app.schemas.trip import TripPlanRequest


def _request(days: int = 2) -> TripPlanRequest:
    return TripPlanRequest(
        destination="上海",
        days=days,
        budget=3000,
        people=2,
        preferences=["城市漫步", "本地美食"],
        avoid=[],
        travel_style="balanced",
    )


def _stop(
    name: str,
    sequence: int,
    lat: float | None,
    lng: float | None,
    place_type: PlaceType = PlaceType.ATTRACTION,
) -> RouteStop:
    return RouteStop(
        sequence=sequence,
        time_period="上午" if place_type == PlaceType.ATTRACTION else "晚餐",
        place_type=place_type,
        name=name,
        address=f"{name}地址",
        lat=lat,
        lng=lng,
        estimated_cost=80,
        estimated_duration=120,
        transport_note="测试路线停靠点。",
    )


def _route_plan(groups: list[DailyRouteGroup]) -> RoutePlan:
    return RoutePlan(daily_route_groups=groups, warnings=[])


def test_hotel_area_schema_keeps_recommended_area_reason_and_warning() -> None:
    area = RecommendedHotelArea(
        name="人民广场周边",
        priority=1,
        center_lat=31.23,
        center_lng=121.47,
        reason="位于两天路线中心，便于减少往返时间。",
        suitable_for="两日及以上行程的中心住宿区域。",
        related_days=[1, 2],
        warnings=["预算较低时需要放宽酒店星级。"],
    )
    plan = HotelAreaPlan(
        recommended_hotel_areas=[area],
        strategy_summary="优先选择路线中心区域。",
        warnings=[],
    )

    assert plan.recommended_hotel_areas[0].name == "人民广场周边"
    assert plan.recommended_hotel_areas[0].related_days == [1, 2]
    assert "路线中心" in plan.strategy_summary


def test_hotel_area_selector_uses_start_and_end_area_for_one_day_trip() -> None:
    route_plan = _route_plan(
        [
            DailyRouteGroup(
                day=1,
                area_summary="外滩附近",
                stops=[
                    _stop("外滩", 1, 31.240, 121.490),
                    _stop("豫园", 2, 31.228, 121.492),
                ],
                route_summary="Day 1：外滩 → 豫园",
                warnings=[],
            )
        ]
    )

    result = hotel_area_selector(TripGraphState(request=_request(days=1), route_plan=route_plan))
    hotel_area_plan = result["hotel_area_plan"]

    assert isinstance(hotel_area_plan, HotelAreaPlan)
    assert hotel_area_plan.recommended_hotel_areas[0].name == "外滩附近起终点区域"
    assert hotel_area_plan.recommended_hotel_areas[0].related_days == [1]
    assert "靠近当天路线起点或终点" in hotel_area_plan.recommended_hotel_areas[0].reason


def test_hotel_area_selector_uses_overall_center_for_two_day_trip() -> None:
    route_plan = _route_plan(
        [
            DailyRouteGroup(
                day=1,
                area_summary="外滩附近",
                stops=[
                    _stop("外滩", 1, 31.240, 121.490),
                    _stop("南京路餐厅", 2, 31.235, 121.475, PlaceType.FOOD),
                ],
                route_summary="Day 1：外滩 → 南京路餐厅",
                warnings=[],
            ),
            DailyRouteGroup(
                day=2,
                area_summary="人民广场附近",
                stops=[
                    _stop("人民广场", 1, 31.230, 121.470),
                    _stop("新天地", 2, 31.220, 121.470),
                ],
                route_summary="Day 2：人民广场 → 新天地",
                warnings=[],
            ),
        ]
    )

    result = hotel_area_selector(TripGraphState(request=_request(days=2), route_plan=route_plan))
    hotel_area_plan = result["hotel_area_plan"]

    assert hotel_area_plan.recommended_hotel_areas[0].name == "上海路线中心区域"
    assert hotel_area_plan.recommended_hotel_areas[0].related_days == [1, 2]
    assert hotel_area_plan.recommended_hotel_areas[0].center_lat == 31.231
    assert hotel_area_plan.recommended_hotel_areas[0].center_lng == 121.476


def test_hotel_area_selector_warns_when_multi_day_route_span_is_large() -> None:
    route_plan = _route_plan(
        [
            DailyRouteGroup(
                day=1,
                area_summary="外滩附近",
                stops=[_stop("外滩", 1, 31.240, 121.490)],
                route_summary="Day 1：外滩",
                warnings=[],
            ),
            DailyRouteGroup(
                day=2,
                area_summary="人民广场附近",
                stops=[_stop("人民广场", 1, 31.230, 121.470)],
                route_summary="Day 2：人民广场",
                warnings=[],
            ),
            DailyRouteGroup(
                day=3,
                area_summary="迪士尼附近",
                stops=[_stop("迪士尼", 1, 31.145, 121.657)],
                route_summary="Day 3：迪士尼",
                warnings=[],
            ),
        ]
    )

    result = hotel_area_selector(TripGraphState(request=_request(days=3), route_plan=route_plan))
    hotel_area_plan = result["hotel_area_plan"]

    assert hotel_area_plan.recommended_hotel_areas[0].name == "上海主要景点分布重心区域"
    assert any("路线跨度较大" in warning for warning in hotel_area_plan.warnings)
    assert any("换酒店" in warning for warning in hotel_area_plan.recommended_hotel_areas[0].warnings)
