from app.graphs.trip_state import TripGraphState
from app.schemas.trip import TripPlanResponse


def final_output(state: TripGraphState) -> dict:
    """输出最终结构化结果。

    最后一层仍使用 Pydantic 严格校验，防止中间节点修改 state 后破坏 API 契约。
    """

    plan = TripPlanResponse.model_validate(state["plan"])
    verification = state.get("verification", {})
    if verification.get("errors"):
        plan = plan.model_copy(update={"warnings": [*plan.warnings, *verification["errors"]]})
    return {"plan": plan}
