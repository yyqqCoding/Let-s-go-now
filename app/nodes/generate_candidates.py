from app.graphs.trip_state import TripGraphState
from app.nodes.merge_candidates import merge_candidate_results
from app.nodes.research_sources import amap_poi_research, dianping_research, fallback_llm_research, xiaohongshu_research


def generate_candidates(state: TripGraphState) -> dict:
    """生成并合并候选池。

    V0.3 开始拆出 research 子流程。
    外部来源未启用时只返回来源状态，真实候选由 fallback_llm_research 生成。
    """

    request = state["request"]
    source_results = [
        xiaohongshu_research(request),
        dianping_research(request),
        amap_poi_research(request),
        fallback_llm_research(request),
    ]
    return {"candidates": merge_candidate_results(request=request, source_results=source_results)}
