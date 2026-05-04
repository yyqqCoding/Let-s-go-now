from pydantic import BaseModel, ConfigDict, Field


class RecommendedHotelArea(BaseModel):
    """推荐住宿区域。

    这是 V0.6 `hotel_area_selector` 的最小输出单元，只描述“住在哪个区域更合适”，
    不描述具体酒店。这样后续接入 `hotel_research` 时，可以把区域作为搜索条件，
    避免在路线未确定前提前生成不稳定的酒店推荐。
    """

    # 禁止额外字段，保证后续酒店搜索节点可以稳定消费该结构。
    model_config = ConfigDict(extra="forbid")

    # 区域名称不是地图 POI 名称，而是面向用户和后续搜索节点的语义化区域描述。
    name: str = Field(..., min_length=1)
    # 优先级从 1 开始，便于未来多个区域候选时按顺序搜索或展示。
    priority: int = Field(..., ge=1)
    # 区域中心点允许为空；当路线缺少坐标时，仍可给出文字区域建议。
    center_lat: float | None = None
    center_lng: float | None = None
    # 推荐理由需要说明为什么这个区域能减少通勤或匹配行程。
    reason: str = Field(..., min_length=1)
    # 适用场景用于后续酒店选择节点区分“全程住一个区域”还是“某天可换酒店”。
    suitable_for: str = Field(..., min_length=1)
    # 该区域主要服务哪些天的路线，后续可以用来做分日酒店策略。
    related_days: list[int] = Field(default_factory=list)
    # 区域级风险提示，例如跨度较大、预算偏紧或坐标不足。
    warnings: list[str] = Field(default_factory=list)


class HotelAreaPlan(BaseModel):
    """V0.6 酒店区域选择结果。

    当前阶段只完成“路线反推住宿区域”，不搜索酒店、不选择酒店、不调用模型。
    `build_itinerary` 暂时不消费该结构，V0.7 重构时再把酒店区域纳入行程表达。
    """

    model_config = ConfigDict(extra="forbid")

    # 推荐区域列表。当前通常只给一个主区域，后续可扩展为主区域 + 换酒店备选区域。
    recommended_hotel_areas: list[RecommendedHotelArea] = Field(default_factory=list)
    # 对本次住宿策略的整体说明，方便 Swagger 手工验收。
    strategy_summary: str = Field(..., min_length=1)
    # 全局提示，例如所有路线都缺少坐标或跨区明显。
    warnings: list[str] = Field(default_factory=list)
