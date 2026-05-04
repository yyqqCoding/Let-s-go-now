from app.graphs.trip_state import TripGraphState
from app.nodes.select_core_places import select_core_places
from app.schemas.candidates import CandidatePlace, CandidatePool, PlaceType
from app.schemas.selection import SelectedPlaces
from app.schemas.trip import TripPlanRequest


def _candidate(
    name: str,
    place_type: PlaceType,
    tags: list[str],
    reason: str,
    confidence: float,
    estimated_cost: float = 50,
) -> CandidatePlace:
    return CandidatePlace(
        name=name,
        type=place_type,
        source="fallback_llm_research",
        address=f"{name}地址",
        lat=None,
        lng=None,
        tags=tags,
        reason=reason,
        estimated_cost=estimated_cost,
        estimated_duration=120,
        confidence=confidence,
        raw_evidence=f"{name}候选证据",
    )


def _request(travel_style: str = "relaxed") -> TripPlanRequest:
    return TripPlanRequest(
        destination="北京",
        days=2,
        budget=2000,
        people=2,
        preferences=["历史文化", "本地美食"],
        avoid=["购物"],
        travel_style=travel_style,
    )


def test_selected_places_schema_keeps_attractions_and_restaurants_separate() -> None:
    attraction = _candidate("故宫", PlaceType.ATTRACTION, ["历史文化"], "历史文化核心景点。", 0.9)
    restaurant = _candidate("护国寺小吃", PlaceType.FOOD, ["本地美食"], "北京本地小吃。", 0.8)

    selected = SelectedPlaces(
        selected_attractions=[attraction],
        selected_restaurants=[restaurant],
        selection_notes=["按偏好和置信度选择。"],
        warnings=[],
    )

    assert selected.selected_attractions == [attraction]
    assert selected.selected_restaurants == [restaurant]


def test_select_core_places_filters_avoid_and_prefers_matching_preferences() -> None:
    request = _request(travel_style="relaxed")
    pool = CandidatePool(
        destination="北京",
        preferences=request.preferences,
        avoid=request.avoid,
        attractions=[
            _candidate("故宫", PlaceType.ATTRACTION, ["历史文化"], "符合历史文化偏好。", 0.7),
            _candidate("高端购物中心", PlaceType.ATTRACTION, ["购物"], "购物商场，不应进入结果。", 0.99),
            _candidate("天坛", PlaceType.ATTRACTION, ["历史文化"], "历史文化景点。", 0.8),
            _candidate("城市观景台", PlaceType.ATTRACTION, ["城市风光"], "置信度高但偏好不匹配。", 0.95),
        ],
        foods=[
            _candidate("护国寺小吃", PlaceType.FOOD, ["本地美食"], "符合本地美食偏好。", 0.7),
            _candidate("商场快餐", PlaceType.FOOD, ["购物"], "位于购物中心，不应进入结果。", 0.95),
            _candidate("炸酱面老店", PlaceType.FOOD, ["本地美食"], "北京本地美食。", 0.8),
        ],
        source_status=[],
    )

    result = select_core_places(TripGraphState(request=request, candidates=pool))
    selected = result["selected_places"]

    assert isinstance(selected, SelectedPlaces)
    assert [place.name for place in selected.selected_attractions] == ["天坛", "故宫", "城市观景台"]
    assert [place.name for place in selected.selected_restaurants] == ["炸酱面老店", "护国寺小吃"]
    assert all("购物" not in place.name for place in selected.selected_attractions)
    assert all("购物" not in place.reason for place in selected.selected_restaurants)


def test_select_core_places_uses_travel_style_to_limit_attractions() -> None:
    request = _request(travel_style="balanced")
    pool = CandidatePool(
        destination="北京",
        preferences=request.preferences,
        avoid=[],
        attractions=[
            _candidate(f"历史景点{i}", PlaceType.ATTRACTION, ["历史文化"], "历史文化景点。", 0.9 - i * 0.01)
            for i in range(10)
        ],
        foods=[
            _candidate(f"本地餐厅{i}", PlaceType.FOOD, ["本地美食"], "本地美食餐厅。", 0.8 - i * 0.01)
            for i in range(5)
        ],
        source_status=[],
    )

    result = select_core_places(TripGraphState(request=request, candidates=pool))
    selected = result["selected_places"]

    assert len(selected.selected_attractions) == 8
    assert len(selected.selected_restaurants) == 2
