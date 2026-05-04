from app.graphs.trip_state import TripGraphState


def verify_plan(state: TripGraphState) -> dict:
    """检查计划结果的基础一致性。

    这里先做确定性校验：目的地、天数、预算字段必须和请求一致。
    校验结果进入 state，V0.8 增强后可用于触发 repair_plan。
    """

    request = state["request"]
    plan = state["plan"]
    errors: list[str] = []
    warnings = list(plan.warnings)

    if plan.destination != request.destination:
        errors.append("目的地与用户输入不一致")
    if len(plan.days) != request.days:
        errors.append("行程天数与用户输入不一致")
    if plan.budget.total_budget != request.budget:
        errors.append("总预算与用户输入不一致")

    return {
        "verification": {
            "is_valid": not errors,
            "errors": errors,
            "warnings": warnings,
        }
    }
