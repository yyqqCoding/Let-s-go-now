from app.graphs.trip_state import TripGraphState
from app.schemas.hotels import HotelCandidatePool, HotelResearchSourceStatus


def hotel_research(state: TripGraphState) -> dict:
    """根据推荐住宿区域生成酒店候选池。

    V0.6 当前只打通结构化流程：读取 `hotel_area_plan` 中的推荐区域，
    返回酒店候选池和来源状态。外部酒店来源尚未接入时必须返回空候选，
    不能填充虚构酒店，避免后续行程把不可验证的信息当作真实推荐。
    """

    request = state["request"]
    hotel_area_plan = state["hotel_area_plan"]
    area_names = [area.name for area in hotel_area_plan.recommended_hotel_areas]

    status = HotelResearchSourceStatus(
        source="hotel_research",
        status="not_enabled",
        message="外部酒店来源尚未接入，当前仅保留推荐住宿区域。",
    )

    return {
        "hotel_candidates": HotelCandidatePool(
            destination=request.destination,
            recommended_area_names=area_names,
            candidates=[],
            source_status=[status],
            warnings=["外部酒店来源尚未接入，暂不生成具体酒店候选。"],
        )
    }
