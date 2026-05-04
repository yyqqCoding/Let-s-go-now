import pytest

from app.graphs.trip_state import TripGraphState
from app.nodes.build_itinerary import build_itinerary
from app.schemas.candidates import PlaceType
from app.schemas.hotels import HotelAreaPlan, HotelCandidate, HotelSelection, RecommendedHotelArea
from app.schemas.routes import DailyRouteGroup, RoutePlan, RouteStop
from app.schemas.trip import TripPlanRequest


def _request(days: int = 2) -> TripPlanRequest:
    return TripPlanRequest(
        destination="杭州",
        days=days,
        budget=2000,
        people=2,
        preferences=["自然风景", "本地美食"],
        avoid=[],
        travel_style="balanced",
    )


def _stop(
    name: str,
    sequence: int,
    time_period: str,
    place_type: PlaceType,
    cost: float,
) -> RouteStop:
    return RouteStop(
        sequence=sequence,
        time_period=time_period,
        place_type=place_type,
        name=name,
        address=f"{name}地址",
        lat=30.25,
        lng=120.13,
        estimated_cost=cost,
        estimated_duration=120,
        transport_note=f"{name}之后按路线顺序继续。",
    )


def _route_plan() -> RoutePlan:
    return RoutePlan(
        daily_route_groups=[
            DailyRouteGroup(
                day=1,
                area_summary="西湖周边",
                stops=[
                    _stop("西湖", 1, "上午", PlaceType.ATTRACTION, 0),
                    _stop("知味观", 2, "午餐", PlaceType.FOOD, 80),
                ],
                route_summary="Day 1：西湖 → 知味观",
                warnings=["当天部分通勤时间待地图能力补齐。"],
            ),
            DailyRouteGroup(
                day=2,
                area_summary="西溪湿地周边",
                stops=[
                    _stop("西溪湿地", 1, "上午", PlaceType.ATTRACTION, 80),
                ],
                route_summary="Day 2：西溪湿地",
                warnings=[],
            ),
        ],
        warnings=["路线为粗略排序，未计算真实通勤。"],
    )


def _hotel_area_plan() -> HotelAreaPlan:
    return HotelAreaPlan(
        recommended_hotel_areas=[
            RecommendedHotelArea(
                name="西湖与武林广场之间",
                priority=1,
                center_lat=30.26,
                center_lng=120.16,
                reason="靠近两天路线中心，便于减少往返时间。",
                suitable_for="两日行程的中心住宿区域。",
                related_days=[1, 2],
                warnings=[],
            )
        ],
        strategy_summary="优先住在路线中心区域。",
        warnings=["酒店区域基于粗略坐标计算。"],
    )


def _hotel(name: str = "西湖精选酒店") -> HotelCandidate:
    return HotelCandidate(
        name=name,
        source="hotel_research",
        area_name="西湖与武林广场之间",
        address=f"{name}地址",
        lat=30.26,
        lng=120.16,
        price_per_night=450,
        rating=4.7,
        tags=["交通方便"],
        reason="靠近路线中心。",
        confidence=0.9,
        raw_evidence="测试酒店候选。",
    )


def test_build_itinerary_uses_route_stops_as_day_activities(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_if_llm_is_used(node_name: str):
        raise AssertionError("build_itinerary 不应再调用完整规划 LLM")

    monkeypatch.setattr("app.nodes.build_itinerary.get_trip_planner_llm", _raise_if_llm_is_used, raising=False)

    result = build_itinerary(
        TripGraphState(
            request=_request(),
            route_plan=_route_plan(),
            hotel_area_plan=_hotel_area_plan(),
            hotel_selection=HotelSelection(
                selected_hotel=_hotel(),
                hotel_reason="预算内且靠近路线中心。",
                backup_hotels=[],
                warnings=[],
            ),
        )
    )

    plan = result["plan"]
    assert plan.destination == "杭州"
    assert len(plan.days) == 2
    assert [activity.place for activity in plan.days[0].activities[:2]] == ["西湖", "知味观"]
    assert plan.days[0].activities[0].type == "attraction"
    assert plan.days[0].activities[1].type == "food"


def test_build_itinerary_adds_selected_hotel_to_each_day() -> None:
    result = build_itinerary(
        TripGraphState(
            request=_request(),
            route_plan=_route_plan(),
            hotel_area_plan=_hotel_area_plan(),
            hotel_selection=HotelSelection(
                selected_hotel=_hotel("西湖精选酒店"),
                hotel_reason="预算内且靠近路线中心。",
                backup_hotels=[],
                warnings=[],
            ),
        )
    )

    plan = result["plan"]
    hotel_activities = [day.activities[-1] for day in plan.days]
    assert all(activity.type == "hotel" for activity in hotel_activities)
    assert all(activity.place == "西湖精选酒店" for activity in hotel_activities)
    assert all(activity.estimated_cost == 450 for activity in hotel_activities)


def test_build_itinerary_adds_recommended_area_when_no_hotel_is_selected() -> None:
    result = build_itinerary(
        TripGraphState(
            request=_request(),
            route_plan=_route_plan(),
            hotel_area_plan=_hotel_area_plan(),
            hotel_selection=HotelSelection(
                selected_hotel=None,
                hotel_reason="酒店来源尚未返回可用候选。",
                backup_hotels=[],
                warnings=["没有可用酒店候选，当前仅能保留推荐住宿区域。"],
            ),
        )
    )

    plan = result["plan"]
    hotel_activity = plan.days[0].activities[-1]
    assert hotel_activity.type == "hotel"
    assert hotel_activity.place == "推荐住宿区域：西湖与武林广场之间"
    assert "酒店来源尚未返回可用候选" in hotel_activity.reason
    assert any("没有可用酒店候选" in warning for warning in plan.warnings)


def test_build_itinerary_uses_user_facing_theme_without_internal_diagnostics() -> None:
    result = build_itinerary(
        TripGraphState(
            request=_request(),
            route_plan=_route_plan(),
            hotel_area_plan=_hotel_area_plan(),
            hotel_selection=HotelSelection(
                selected_hotel=None,
                hotel_reason="酒店来源尚未返回可用候选。",
                backup_hotels=[],
                warnings=[],
            ),
        )
    )

    plan = result["plan"]
    assert plan.days[0].theme == "杭州第1天自然风景与本地美食路线"
    assert "缺少坐标" not in plan.days[0].theme
    assert "按候选顺序" not in plan.days[0].theme


def test_build_itinerary_adds_dinner_guidance_when_route_has_no_dinner() -> None:
    result = build_itinerary(
        TripGraphState(
            request=_request(),
            route_plan=_route_plan(),
            hotel_area_plan=_hotel_area_plan(),
            hotel_selection=HotelSelection(
                selected_hotel=None,
                hotel_reason="酒店来源尚未返回可用候选。",
                backup_hotels=[],
                warnings=[],
            ),
        )
    )

    day_activities = result["plan"].days[0].activities
    dinner_activity = next(activity for activity in day_activities if activity.time_period == "晚餐")
    assert dinner_activity.type == "food"
    assert dinner_activity.place == "住宿区域附近晚餐"
    assert "西湖与武林广场之间" in dinner_activity.reason


def test_build_itinerary_uses_user_facing_hotel_area_copy() -> None:
    result = build_itinerary(
        TripGraphState(
            request=_request(),
            route_plan=_route_plan(),
            hotel_area_plan=_hotel_area_plan(),
            hotel_selection=HotelSelection(
                selected_hotel=None,
                hotel_reason="酒店来源尚未返回可用候选。",
                backup_hotels=[],
                warnings=[],
            ),
        )
    )

    hotel_activity = result["plan"].days[0].activities[-1]
    assert hotel_activity.type == "hotel"
    assert "建议优先选择西湖与武林广场之间附近住宿" in hotel_activity.tips
    assert "后续接入酒店来源" not in hotel_activity.tips
