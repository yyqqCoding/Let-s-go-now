from app.graphs.trip_state import TripGraphState
from app.schemas.trip import Activity, DayPlan, TravelStyle


def verify_plan(state: TripGraphState) -> dict:
    """检查计划结果是否可用。

    V0.8.2 后，本节点不再只检查目的地和天数，而是把每日结构、餐饮、住宿、
    预算压力、规避项和行程强度都纳入校验。当前只负责“发现问题”，不自动修复；
    repair_plan 会在后续阶段基于这里的 errors / warnings 做调整。
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

    for day in plan.days:
        errors.extend(_validate_day_required_activities(day))
        warnings.extend(_validate_day_density(day, request.travel_style))

    warnings.extend(_validate_budget_pressure(plan.budget.estimated_total_cost, request.budget, warnings))
    warnings.extend(_validate_avoid_terms(plan.days, request.avoid))

    deduped_errors = _deduplicate_messages(errors)
    deduped_warnings = _deduplicate_messages(warnings)
    return {
        "verification": {
            "is_valid": not deduped_errors,
            "errors": deduped_errors,
            "warnings": deduped_warnings,
        }
    }


def _validate_day_required_activities(day: DayPlan) -> list[str]:
    """检查每天是否具备基础活动类型。

    景点、餐饮和住宿是当前行程的最低结构要求。缺失时归为 errors，
    因为最终行程已经无法满足基本展示和用户验收。
    """

    errors: list[str] = []
    activity_types = {activity.type for activity in day.activities}
    if "attraction" not in activity_types:
        errors.append(f"第{day.day}天缺少景点安排")
    if "food" not in activity_types:
        errors.append(f"第{day.day}天缺少餐饮安排")
    if "hotel" not in activity_types:
        errors.append(f"第{day.day}天缺少住宿安排")
    return errors


def _validate_day_density(day: DayPlan, travel_style: TravelStyle) -> list[str]:
    """检查行程是否过满。

    当前只对 relaxed 做强提醒：轻松模式下一天超过 3 个景点时，用户体验通常会变差。
    balanced / intensive 的细粒度阈值留到后续路线和时间模型增强时再做。
    """

    if travel_style != TravelStyle.RELAXED:
        return []

    attraction_count = sum(1 for activity in day.activities if activity.type == "attraction")
    if attraction_count > 3:
        return [f"第{day.day}天行程偏满：relaxed 模式下安排了 {attraction_count} 个景点。"]
    return []


def _validate_budget_pressure(estimated_total_cost: float, total_budget: float, existing_warnings: list[str]) -> list[str]:
    """检查规则估算是否超出预算。"""

    if estimated_total_cost > total_budget:
        if _has_budget_pressure_warning(existing_warnings):
            return []
        return [f"预算估算超出：预计约 {estimated_total_cost:.0f} 元，高于总预算 {total_budget:.0f} 元。"]
    return []


def _has_budget_pressure_warning(warnings: list[str]) -> bool:
    """判断上游是否已经写入预算压力提示。

    estimate_budget 会优先生成更贴近预算拆分的提示；verify_plan 只在缺少该提示时补充，
    避免最终响应出现两条语义重复但文案不同的预算 warning。
    """

    return any("预算可能超出" in warning or "预算估算超出" in warning for warning in warnings)


def _validate_avoid_terms(days: list[DayPlan], avoid_terms: list[str]) -> list[str]:
    """检查最终行程文案是否命中用户规避项。

    这里做简单文本匹配，覆盖地点名、理由和 tips。语义规避会在后续候选生成和选点阶段继续增强。
    """

    if not avoid_terms:
        return []

    warnings: list[str] = []
    normalized_avoid_terms = [term.lower() for term in avoid_terms if term]
    for day in days:
        for activity in day.activities:
            text = _activity_search_text(activity)
            for avoid_term in normalized_avoid_terms:
                if avoid_term in text:
                    warnings.append(f"第{day.day}天活动「{activity.place}」命中规避项：{avoid_term}")
    return warnings


def _activity_search_text(activity: Activity) -> str:
    """把活动可见字段合并成规避项搜索文本。"""

    return " ".join(
        [
            activity.time_period,
            activity.type,
            activity.place,
            activity.reason,
            activity.tips,
        ]
    ).lower()


def _deduplicate_messages(messages: list[str]) -> list[str]:
    """按出现顺序去重校验消息。"""

    deduped: list[str] = []
    seen: set[str] = set()
    for message in messages:
        if message and message not in seen:
            deduped.append(message)
            seen.add(message)
    return deduped
