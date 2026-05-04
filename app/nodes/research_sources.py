from app.llm import get_trip_planner_llm
from app.schemas.candidates import CandidatePlace, ResearchSourceResult
from app.schemas.trip import TripPlanRequest


def xiaohongshu_research(request: TripPlanRequest) -> ResearchSourceResult:
    """小红书研究来源。

    当前阶段尚未接入外部 MCP，因此只返回来源状态，不生成候选数据。
    """

    return _not_enabled_result("xiaohongshu_research")


def dianping_research(request: TripPlanRequest) -> ResearchSourceResult:
    """大众点评研究来源。

    当前阶段尚未接入外部 MCP，因此只返回来源状态，不生成候选数据。
    """

    return _not_enabled_result("dianping_research")


def amap_poi_research(request: TripPlanRequest) -> ResearchSourceResult:
    """高德 POI 研究来源。

    当前阶段尚未接入外部 MCP，因此只返回来源状态，不生成候选数据。
    """

    return _not_enabled_result("amap_poi_research")


def fallback_llm_research(request: TripPlanRequest) -> ResearchSourceResult:
    """真实模型兜底研究来源。

    外部来源未接入前，由 OpenAI 兼容模型生成结构化候选池。
    """

    # 显式传入节点名，确保读取 model_config.toml 中 fallback_llm_research 的专属配置；
    # 如果没有专属配置，则由配置层回退到 openai.default。
    pool = get_trip_planner_llm("fallback_llm_research").generate_candidates(request)
    return ResearchSourceResult(
        source="fallback_llm_research",
        status="enabled",
        # CandidatePool 已经区分 attractions / foods，这里重新合并为单来源结果，
        # 交给 merge_candidates 统一去重和排序，避免不同来源走不同合并规则。
        candidates=[*_normalize_source(pool.attractions), *_normalize_source(pool.foods)],
        message="由真实 OpenAI 兼容模型生成候选。",
    )


def _not_enabled_result(source: str) -> ResearchSourceResult:
    """构造未启用来源结果。

    这里不能填充假候选。未接入 MCP 的来源必须明确返回空列表，
    让候选池真实反映当前系统能力。
    """

    return ResearchSourceResult(source=source, status="not_enabled", candidates=[], message="外部来源尚未接入。")


def _normalize_source(candidates: list[CandidatePlace]) -> list[CandidatePlace]:
    """确保 fallback 输出的候选来源统一为 fallback_llm_research。

    真实模型有时会把 source 写成其它值。这里在进入 merge 前强制修正，
    使来源状态、候选来源和节点名保持一致。
    """

    return [candidate.model_copy(update={"source": "fallback_llm_research"}) for candidate in candidates]
