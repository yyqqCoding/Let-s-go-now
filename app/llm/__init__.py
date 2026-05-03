from app.core.config import get_settings
from app.llm.base import TripPlannerLLM
from app.llm.openai_compatible import OpenAICompatibleTripPlannerLLM


def get_trip_planner_llm() -> TripPlannerLLM:
    # 当前项目已经进入真实模型阶段。所有节点都通过 OpenAI-compatible 客户端调用模型。
    return OpenAICompatibleTripPlannerLLM(get_settings())


__all__ = ["TripPlannerLLM", "get_trip_planner_llm"]
