from app.schemas.candidates import CandidatePlace, CandidatePool, PlaceType, ResearchSourceResult
from app.schemas.trip import TripPlanRequest


def merge_candidate_results(request: TripPlanRequest, source_results: list[ResearchSourceResult]) -> CandidatePool:
    """合并多个来源的候选地点。

    当前去重策略使用“地点名 + 类型”作为键；重复候选保留 confidence 更高的一条。
    这个规则简单、可解释，后续接入经纬度后可升级为名称和距离联合去重。
    """

    # deduped 的 key 使用“标准化名称 + 类型”，避免同名景点和同名餐厅互相覆盖。
    deduped: dict[tuple[str, PlaceType], CandidatePlace] = {}
    for source_result in source_results:
        for candidate in source_result.candidates:
            key = (_normalize_name(candidate.name), candidate.type)
            existing = deduped.get(key)
            # 多来源命中同一个候选时，保留置信度更高的版本。
            # 后续接入真实 POI 后，可以在这里追加 sources 字段或 evidence 聚合。
            if existing is None or candidate.confidence > existing.confidence:
                deduped[key] = candidate

    # 候选池按类型拆开，V0.4 选点时可以分别控制景点数量和餐饮数量。
    attractions = [candidate for candidate in deduped.values() if candidate.type == PlaceType.ATTRACTION]
    foods = [candidate for candidate in deduped.values() if candidate.type == PlaceType.FOOD]

    return CandidatePool(
        destination=request.destination,
        preferences=request.preferences,
        avoid=request.avoid,
        # 置信度高的候选排在前面，让后续节点默认优先处理更可靠的数据。
        attractions=sorted(attractions, key=lambda candidate: candidate.confidence, reverse=True),
        foods=sorted(foods, key=lambda candidate: candidate.confidence, reverse=True),
        # 即使某个来源未启用或失败，也保留状态，方便定位候选不足的原因。
        source_status=[source_result.to_status() for source_result in source_results],
    )


def _normalize_name(name: str) -> str:
    """归一化候选名，用于基础去重。

    目前只去掉大小写和空白差异，例如“西 湖”和“西湖”会视为同一候选。
    不做复杂别名处理，避免在缺少真实 POI id 时误合并不同地点。
    """

    return "".join(name.lower().split())
