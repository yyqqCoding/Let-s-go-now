from app.graphs.trip_state import TripGraphState
from app.nodes.route_optimizer import route_optimizer
from app.schemas.candidates import CandidatePlace, PlaceType
from app.schemas.routes import DailyRouteGroup, RoutePlan, RouteStop
from app.schemas.selection import SelectedPlaces
from app.schemas.trip import TripPlanRequest


def _candidate(
    name: str,
    place_type: PlaceType,
    lat: float | None,
    lng: float | None,
    confidence: float = 0.8,
) -> CandidatePlace:
    return CandidatePlace(
        name=name,
        type=place_type,
        source="fallback_llm_research",
        address=f"{name}地址",
        lat=lat,
        lng=lng,
        tags=["历史文化"] if place_type == PlaceType.ATTRACTION else ["本地美食"],
        reason=f"{name}适合本次旅行。",
        estimated_cost=60,
        estimated_duration=120 if place_type == PlaceType.ATTRACTION else 90,
        confidence=confidence,
        raw_evidence=f"{name}候选证据",
    )


def _request(days: int = 2) -> TripPlanRequest:
    return TripPlanRequest(
        destination="北京",
        days=days,
        budget=3000,
        people=2,
        preferences=["历史文化", "本地美食"],
        avoid=[],
        travel_style="balanced",
    )


def test_route_plan_schema_keeps_daily_groups_and_stops() -> None:
    stop = RouteStop(
        sequence=1,
        time_period="上午",
        place_type=PlaceType.ATTRACTION,
        name="故宫",
        address="故宫地址",
        lat=39.91,
        lng=116.39,
        estimated_cost=60,
        estimated_duration=120,
        transport_note="当天第一个地点。",
    )
    group = DailyRouteGroup(day=1, area_summary="核心城区", stops=[stop], route_summary="上午游览故宫。", warnings=[])
    plan = RoutePlan(daily_route_groups=[group], warnings=[])

    assert plan.daily_route_groups[0].stops[0].name == "故宫"
    assert plan.daily_route_groups[0].stops[0].time_period == "上午"


def test_route_optimizer_groups_nearby_attractions_by_day_and_inserts_restaurants() -> None:
    request = _request(days=2)
    selected_places = SelectedPlaces(
        selected_attractions=[
            _candidate("故宫", PlaceType.ATTRACTION, 39.91, 116.39, 0.9),
            _candidate("景山公园", PlaceType.ATTRACTION, 39.92, 116.39, 0.88),
            _candidate("颐和园", PlaceType.ATTRACTION, 39.99, 116.27, 0.87),
            _candidate("圆明园", PlaceType.ATTRACTION, 40.01, 116.30, 0.86),
        ],
        selected_restaurants=[
            _candidate("故宫附近餐厅", PlaceType.FOOD, 39.91, 116.40, 0.8),
            _candidate("颐和园附近餐厅", PlaceType.FOOD, 40.00, 116.29, 0.8),
        ],
        selection_notes=[],
        warnings=[],
    )

    result = route_optimizer(TripGraphState(request=request, selected_places=selected_places))
    route_plan = result["route_plan"]

    assert isinstance(route_plan, RoutePlan)
    assert len(route_plan.daily_route_groups) == 2
    assert [stop.name for stop in route_plan.daily_route_groups[0].stops] == ["故宫", "故宫附近餐厅", "景山公园"]
    assert [stop.name for stop in route_plan.daily_route_groups[1].stops] == ["颐和园", "颐和园附近餐厅", "圆明园"]
    assert route_plan.daily_route_groups[0].stops[1].time_period == "午餐"
    assert route_plan.daily_route_groups[1].stops[1].time_period == "午餐"


def test_route_optimizer_records_warning_when_restaurants_are_not_enough() -> None:
    request = _request(days=2)
    selected_places = SelectedPlaces(
        selected_attractions=[
            _candidate("故宫", PlaceType.ATTRACTION, 39.91, 116.39, 0.9),
            _candidate("颐和园", PlaceType.ATTRACTION, 39.99, 116.27, 0.87),
        ],
        selected_restaurants=[],
        selection_notes=[],
        warnings=[],
    )

    result = route_optimizer(TripGraphState(request=request, selected_places=selected_places))
    route_plan = result["route_plan"]

    assert len(route_plan.daily_route_groups) == 2
    assert "餐饮候选不足" in route_plan.warnings[0]
