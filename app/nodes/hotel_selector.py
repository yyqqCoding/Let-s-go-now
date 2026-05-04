from math import ceil

from app.graphs.trip_state import TripGraphState
from app.schemas.hotels import HotelCandidate, HotelSelection


def hotel_selector(state: TripGraphState) -> dict:
    """从酒店候选池中选择本次行程的住宿。

    当前选择逻辑保持确定性：先过滤用户规避项，再优先选择预算内酒店，
    同等预算条件下按评分、置信度和价格排序。候选为空时返回显式空选择，
    让后续节点和校验逻辑知道“还没有具体酒店”，而不是误以为已经完成住宿选择。
    """

    request = state["request"]
    hotel_candidates = state["hotel_candidates"]
    warnings = list(hotel_candidates.warnings)

    usable_candidates = [
        candidate for candidate in hotel_candidates.candidates if not _matches_avoid(candidate, request.avoid)
    ]
    if not usable_candidates:
        warnings.append("没有可用酒店候选，当前仅能保留推荐住宿区域。")
        return {
            "hotel_selection": HotelSelection(
                selected_hotel=None,
                hotel_reason="酒店来源尚未返回可用候选，暂不选择具体酒店。",
                backup_hotels=[],
                warnings=warnings,
            )
        }

    max_price_per_night = _estimate_max_price_per_night(
        total_budget=request.budget,
        people=request.people,
        days=request.days,
    )
    ranked_candidates = sorted(
        usable_candidates,
        key=lambda candidate: _ranking_key(candidate, max_price_per_night),
    )
    selected_hotel = ranked_candidates[0]
    backup_hotels = [
        candidate
        for candidate in ranked_candidates[1:3]
        if candidate.price_per_night <= max_price_per_night
    ]

    if selected_hotel.price_per_night > max_price_per_night:
        warnings.append("未找到预算范围内的酒店候选，已选择综合评分最高的备选。")

    return {
        "hotel_selection": HotelSelection(
            selected_hotel=selected_hotel,
            hotel_reason=_build_hotel_reason(selected_hotel, max_price_per_night),
            backup_hotels=backup_hotels,
            warnings=warnings,
        )
    }


def _estimate_max_price_per_night(total_budget: float, people: int, days: int) -> float:
    """估算当前总预算下可接受的每晚房价。

    住宿先按总预算的 40% 估算，这是未做精细预算拆分前的保守比例。
    房间数按每间 2 人估算；一日行程也保留 1 晚兜底，避免除零并兼容需要住宿的玩法。
    """

    nights = max(days - 1, 1)
    room_count = max(ceil(people / 2), 1)
    return total_budget * 0.4 / nights / room_count


def _ranking_key(candidate: HotelCandidate, max_price_per_night: float) -> tuple[bool, float, float, float]:
    """生成酒店排序键。

    排序顺序为：预算内优先、评分高优先、置信度高优先、价格低优先。
    Python 默认升序，因此评分和置信度使用负数。
    """

    over_budget = candidate.price_per_night > max_price_per_night
    return (over_budget, -candidate.rating, -candidate.confidence, candidate.price_per_night)


def _matches_avoid(candidate: HotelCandidate, avoid: list[str]) -> bool:
    """判断酒店候选是否命中用户规避项。

    规避项同时匹配名称、标签和推荐理由，避免例如“酒吧街”“高消费”等不适合偏好进入最终选择。
    """

    if not avoid:
        return False

    searchable_text = " ".join([candidate.name, candidate.reason, *candidate.tags]).lower()
    return any(item.lower() in searchable_text for item in avoid)


def _build_hotel_reason(candidate: HotelCandidate, max_price_per_night: float) -> str:
    """生成选择理由，说明预算和路线区域两个关键依据。"""

    budget_text = "符合预算" if candidate.price_per_night <= max_price_per_night else "高于当前预算参考线"
    return (
        f"{candidate.name}{budget_text}，位于{candidate.area_name}，"
        f"评分 {candidate.rating}，适合作为本次路线后的住宿选择。"
    )
