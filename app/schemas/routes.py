from pydantic import BaseModel, ConfigDict, Field

from app.schemas.candidates import PlaceType


class RouteStop(BaseModel):
    """单个路线停靠点。

    RouteStop 是 route_optimizer 的最小输出单元，表示某一天中的一个景点或餐饮安排。
    当前阶段只做顺序和时间段安排，不计算真实地图通勤。
    """

    # 禁止额外字段，确保后续 build_itinerary 或 route 展示层能稳定消费。
    model_config = ConfigDict(extra="forbid")

    # 当天内部顺序，从 1 开始。
    sequence: int = Field(..., ge=1)
    # 上午、午餐、下午、晚餐等时间段，用于后续生成自然语言行程。
    time_period: str = Field(..., min_length=1)
    # 地点类型：景点或餐饮。
    place_type: PlaceType
    # 地点名称和地址，来自 CandidatePlace。
    name: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)
    # 经纬度允许为空；未接入地图 MCP 前，候选可能没有稳定坐标。
    lat: float | None = None
    lng: float | None = None
    # 单人预计费用和停留时长，后续预算与时间安排会复用。
    estimated_cost: float = Field(..., ge=0)
    estimated_duration: int = Field(..., gt=0)
    # 当前只写规则说明；真实通勤时间会在接入地图能力后替换。
    transport_note: str = Field(..., min_length=1)


class DailyRouteGroup(BaseModel):
    """某一天的路线分组。"""

    model_config = ConfigDict(extra="forbid")

    # 第几天，从 1 开始。
    day: int = Field(..., ge=1)
    # 对当天地点区域的简短描述。
    area_summary: str = Field(..., min_length=1)
    # 当天按顺序排列的停靠点。
    stops: list[RouteStop] = Field(default_factory=list)
    # 当天路线摘要，用于 Swagger 验收和后续行程文案。
    route_summary: str = Field(..., min_length=1)
    # 当天路线软性问题，例如缺少餐饮或坐标不足。
    warnings: list[str] = Field(default_factory=list)


class RoutePlan(BaseModel):
    """V0.5 路线优化结果。

    这是 V0.5 的核心产物，也是 V0.6 酒店区域选择和 V0.7 行程表达的输入。
    它只负责“每天去哪些点、按什么顺序”，不负责选择酒店或生成最终文案。
    """

    model_config = ConfigDict(extra="forbid")

    # 每天的路线分组，数量应尽量等于用户输入 days。
    daily_route_groups: list[DailyRouteGroup] = Field(default_factory=list)
    # 全局路线 warning，例如餐饮候选不足、坐标缺失导致只能按置信度排序。
    warnings: list[str] = Field(default_factory=list)
