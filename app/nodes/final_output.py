from app.graphs.trip_state import TripGraphState
from app.schemas.trip import TripPlanResponse


def final_output(state: TripGraphState) -> dict:
    """输出最终结构化结果。

    最后一层仍使用 Pydantic 严格校验，防止中间节点修改 state 后破坏 API 契约。
    """

    plan = TripPlanResponse.model_validate(state["plan"])
    verification = state.get("verification", {})
    verification_messages = [*verification.get("errors", []), *verification.get("warnings", [])]
    if verification_messages:
        plan = plan.model_copy(update={"warnings": _deduplicate_warnings([*plan.warnings, *verification_messages])})
    return {"plan": plan}


def _deduplicate_warnings(warnings: list[str]) -> list[str]:
    """合并最终 warning 时按顺序去重。

    上游节点和 verify_plan 可能描述同一个问题，例如预算超出。
    最终输出层去重可以减少 Swagger 响应中的重复提示。
    """

    deduped: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning and warning not in seen:
            deduped.append(warning)
            seen.add(warning)
    return deduped
