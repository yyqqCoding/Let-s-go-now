from app.graphs.trip_state import TripGraphState
from app.schemas.candidates import CandidatePlace, CandidatePool, PlaceType
from app.schemas.selection import SelectedPlaces
from app.schemas.trip import TravelStyle


_ATTRACTIONS_PER_DAY = {
    TravelStyle.RELAXED: 3,
    TravelStyle.BALANCED: 4,
    TravelStyle.INTENSIVE: 5,
}


def select_core_places(state: TripGraphState) -> dict:
    """从候选池中选择本次旅行真正要安排的核心地点。

    V0.4 只做确定性选点，不调用模型、不做路线顺序、不做酒店推荐。
    这样后续 route_optimizer 可以基于稳定的 selected_places 继续规划路线。
    """

    request = state["request"]
    candidates = state["candidates"]
    max_attractions = request.days * _ATTRACTIONS_PER_DAY[request.travel_style]
    min_restaurants = request.days

    filtered_attractions = _filter_avoid(candidates.attractions, request.avoid)
    filtered_foods = _filter_avoid(candidates.foods, request.avoid)

    selected_attractions = _rank_candidates(filtered_attractions, request.preferences)[:max_attractions]
    selected_restaurants = _rank_candidates(filtered_foods, request.preferences)[:min_restaurants]

    warnings: list[str] = []
    if len(selected_attractions) < max_attractions:
        warnings.append(f"可用景点候选不足，当前选择 {len(selected_attractions)} 个，目标最多 {max_attractions} 个。")
    if len(selected_restaurants) < min_restaurants:
        warnings.append(f"可用餐饮候选不足，当前选择 {len(selected_restaurants)} 个，目标至少 {min_restaurants} 个。")

    selected_places = SelectedPlaces(
        selected_attractions=selected_attractions,
        selected_restaurants=selected_restaurants,
        selection_notes=[
            f"按 {request.travel_style.value} 节奏选择景点，最多 {max_attractions} 个。",
            f"按每天至少 1 个餐饮点选择餐厅，目标 {min_restaurants} 个。",
            "已过滤命中 avoid 的候选，并优先选择匹配 preferences 的候选。",
        ],
        warnings=warnings,
    )
    return {"selected_places": selected_places}


def _filter_avoid(candidates: list[CandidatePlace], avoid: list[str]) -> list[CandidatePlace]:
    """过滤命中用户 avoid 的候选。

    当前没有真实分类体系，因此先在名称、地址、标签、理由和证据文本中做包含匹配。
    后续接入真实 POI 分类后，可以替换为更精确的类别过滤。
    """

    avoid_terms = [term.strip().lower() for term in avoid if term.strip()]
    if not avoid_terms:
        return candidates

    return [candidate for candidate in candidates if not _contains_any_term(_candidate_search_text(candidate), avoid_terms)]


def _rank_candidates(candidates: list[CandidatePlace], preferences: list[str]) -> list[CandidatePlace]:
    """按偏好匹配和置信度排序候选。

    排序规则先看偏好匹配数量，再看 confidence。
    这样可以避免“不符合偏好但置信度高”的地点压过真正贴合用户需求的地点。
    """

    preference_terms = [preference.strip().lower() for preference in preferences if preference.strip()]
    return sorted(
        candidates,
        key=lambda candidate: (
            _preference_match_count(candidate, preference_terms),
            candidate.confidence,
            -candidate.estimated_cost,
        ),
        reverse=True,
    )


def _preference_match_count(candidate: CandidatePlace, preference_terms: list[str]) -> int:
    """计算候选命中的偏好数量。"""

    search_text = _candidate_search_text(candidate)
    return sum(1 for preference in preference_terms if preference in search_text)


def _contains_any_term(text: str, terms: list[str]) -> bool:
    """判断文本是否包含任意关键词。"""

    return any(term in text for term in terms)


def _candidate_search_text(candidate: CandidatePlace) -> str:
    """拼接候选可搜索文本。

    所有文本统一转小写，便于偏好匹配和 avoid 过滤复用同一套基础逻辑。
    """

    return " ".join(
        [
            candidate.name,
            candidate.type.value if isinstance(candidate.type, PlaceType) else str(candidate.type),
            candidate.source,
            candidate.address,
            " ".join(candidate.tags),
            candidate.reason,
            candidate.raw_evidence,
        ]
    ).lower()
