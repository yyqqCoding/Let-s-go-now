from app.graphs.trip_state import TripGraphState


def estimate_budget(state: TripGraphState) -> dict:
    """校正预算信息。

    V0.2 先保证返回结果中的总预算严格等于用户输入。
    后续 V0.8 会把这里替换成规则化预算拆分，不再完全依赖模型估算。
    """

    request = state["request"]
    plan = state["plan"].model_copy(deep=True)
    plan.budget.total_budget = request.budget
    plan.budget.estimated_total_cost = min(plan.budget.estimated_total_cost, request.budget)
    return {"plan": plan}
