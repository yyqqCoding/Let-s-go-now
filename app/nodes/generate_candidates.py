from app.graphs.trip_state import TripGraphState


def generate_candidates(state: TripGraphState) -> dict:
    """生成候选池上下文。

    V0.2 只建立候选池的数据边界，不接外部 MCP，也不写模拟数据。
    真实候选生成会在 V0.3 通过 research 子流程和 fallback LLM 节点补齐。
    """

    intent = state["intent"]
    return {
        "candidates": {
            "destination": intent["destination"],
            "preferences": intent["preferences"],
            "avoid": intent["avoid"],
            "attractions": [],
            "restaurants": [],
            "hotels": [],
            "source_status": [
                {"source": "xiaohongshu_research", "status": "not_enabled"},
                {"source": "dianping_research", "status": "not_enabled"},
                {"source": "amap_poi_research", "status": "not_enabled"},
            ],
        }
    }
