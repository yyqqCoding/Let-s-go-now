from app.core.config import get_settings
from app.llm.base import TripPlannerLLM
from app.llm.openai_compatible import OpenAICompatibleTripPlannerLLM


def get_trip_planner_llm(node_name: str = "build_itinerary") -> TripPlannerLLM:
    # 当前项目已经进入真实模型阶段。所有 LLM 节点都通过 OpenAI-compatible 客户端调用模型。
    # node_name 会映射到 model_config.toml 中的 [openai.nodes.<node_name>] 配置。
    return OpenAICompatibleTripPlannerLLM(get_settings(), node_name=node_name)


__all__ = ["TripPlannerLLM", "get_trip_planner_llm"]
