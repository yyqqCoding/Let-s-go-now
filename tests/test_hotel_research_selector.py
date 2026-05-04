from app.graphs.trip_state import TripGraphState
from app.nodes.hotel_research import hotel_research
from app.nodes.hotel_selector import hotel_selector
from app.schemas.hotels import (
    HotelAreaPlan,
    HotelCandidate,
    HotelCandidatePool,
    HotelSelection,
    RecommendedHotelArea,
)
from app.schemas.trip import TripPlanRequest


def _request(days: int = 3, budget: float = 3000, people: int = 2) -> TripPlanRequest:
    return TripPlanRequest(
        destination="上海",
        days=days,
        budget=budget,
        people=people,
        preferences=["城市漫步", "本地美食"],
        avoid=[],
        travel_style="balanced",
    )


def _hotel_area_plan() -> HotelAreaPlan:
    return HotelAreaPlan(
        recommended_hotel_areas=[
            RecommendedHotelArea(
                name="上海路线中心区域",
                priority=1,
                center_lat=31.231,
                center_lng=121.476,
                reason="位于路线中心，便于减少往返时间。",
                suitable_for="两日及以上行程的中心住宿区域。",
                related_days=[1, 2, 3],
                warnings=[],
            )
        ],
        strategy_summary="优先选择路线中心区域。",
        warnings=[],
    )


def _candidate(
    name: str,
    price_per_night: float,
    rating: float,
    confidence: float,
    area_name: str = "上海路线中心区域",
) -> HotelCandidate:
    return HotelCandidate(
        name=name,
        source="hotel_research",
        area_name=area_name,
        address=f"{name}地址",
        lat=31.231,
        lng=121.476,
        price_per_night=price_per_night,
        rating=rating,
        tags=["交通方便", "路线中心"],
        reason=f"{name}适合作为本次住宿候选。",
        confidence=confidence,
        raw_evidence=f"{name}候选依据。",
    )


def test_hotel_candidate_pool_and_selection_schema_keep_stable_fields() -> None:
    candidate = _candidate("人民广场舒适酒店", price_per_night=420, rating=4.6, confidence=0.82)
    pool = HotelCandidatePool(
        destination="上海",
        recommended_area_names=["上海路线中心区域"],
        candidates=[candidate],
        source_status=[],
        warnings=[],
    )
    selection = HotelSelection(
        selected_hotel=candidate,
        hotel_reason="预算内且靠近路线中心。",
        backup_hotels=[],
        warnings=[],
    )

    assert pool.candidates[0].area_name == "上海路线中心区域"
    assert selection.selected_hotel is not None
    assert selection.selected_hotel.name == "人民广场舒适酒店"


def test_hotel_research_returns_not_enabled_status_without_candidates() -> None:
    request = _request()

    result = hotel_research(TripGraphState(request=request, hotel_area_plan=_hotel_area_plan()))
    hotel_candidates = result["hotel_candidates"]

    assert isinstance(hotel_candidates, HotelCandidatePool)
    assert hotel_candidates.candidates == []
    assert hotel_candidates.recommended_area_names == ["上海路线中心区域"]
    assert hotel_candidates.source_status[0].source == "hotel_research"
    assert hotel_candidates.source_status[0].status == "not_enabled"
    assert "尚未接入" in hotel_candidates.source_status[0].message


def test_hotel_selector_returns_empty_selection_when_candidates_are_unavailable() -> None:
    request = _request()
    hotel_candidates = HotelCandidatePool(
        destination="上海",
        recommended_area_names=["上海路线中心区域"],
        candidates=[],
        source_status=[],
        warnings=["外部酒店来源尚未接入。"],
    )

    result = hotel_selector(TripGraphState(request=request, hotel_candidates=hotel_candidates))
    hotel_selection = result["hotel_selection"]

    assert isinstance(hotel_selection, HotelSelection)
    assert hotel_selection.selected_hotel is None
    assert hotel_selection.backup_hotels == []
    assert any("没有可用酒店候选" in warning for warning in hotel_selection.warnings)


def test_hotel_selector_prefers_budget_matched_high_rating_and_confidence_candidate() -> None:
    request = _request(days=3, budget=3000, people=2)
    expensive = _candidate("高价江景酒店", price_per_night=1600, rating=4.9, confidence=0.95)
    budget_matched = _candidate("人民广场精选酒店", price_per_night=480, rating=4.7, confidence=0.88)
    lower_rating = _candidate("普通快捷酒店", price_per_night=380, rating=4.1, confidence=0.8)
    hotel_candidates = HotelCandidatePool(
        destination="上海",
        recommended_area_names=["上海路线中心区域"],
        candidates=[expensive, budget_matched, lower_rating],
        source_status=[],
        warnings=[],
    )

    result = hotel_selector(TripGraphState(request=request, hotel_candidates=hotel_candidates))
    hotel_selection = result["hotel_selection"]

    assert hotel_selection.selected_hotel is not None
    assert hotel_selection.selected_hotel.name == "人民广场精选酒店"
    assert [hotel.name for hotel in hotel_selection.backup_hotels] == ["普通快捷酒店"]
    assert "预算" in hotel_selection.hotel_reason
