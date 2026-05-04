from app.graphs.trip_state import TripGraphState


def parse_intent(state: TripGraphState) -> dict:
    """解析并标准化用户旅游需求。

    当前阶段 FastAPI 和 Pydantic 已经完成字段校验，所以这里先把请求转换成图内部的
    intent 字典。后续如果需要识别隐藏意图、补齐默认出行时间或交通偏好，可以集中扩展此节点。
    """

    request = state["request"]
    return {
        "intent": {
            "destination": request.destination,
            "days": request.days,
            "budget": request.budget,
            "people": request.people,
            "preferences": request.preferences,
            "avoid": request.avoid,
            "travel_style": request.travel_style.value,
        }
    }
