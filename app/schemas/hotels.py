from typing import Literal

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


class HotelCandidate(BaseModel):
    """酒店候选结构。

    `hotel_research` 后续接入真实酒店来源时，必须先把外部结果转换成这个结构，
    再交给 `hotel_selector` 做确定性选择。当前阶段不会主动生成酒店候选，
    但先固定结构可以避免后续节点之间继续传散乱字典。
    """

    model_config = ConfigDict(extra="forbid")

    # 酒店名称和来源节点名，用于展示、排查和后续多来源合并。
    name: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    # 候选酒店所属推荐住宿区域，必须能追溯到 HotelAreaPlan。
    area_name: str = Field(..., min_length=1)
    # 地址和坐标用于后续地图距离、通勤时间和商圈判断。
    address: str = Field(..., min_length=1)
    lat: float | None = None
    lng: float | None = None
    # 每晚价格按人民币估算；后续预算节点会结合晚数和房间数复算住宿费用。
    price_per_night: float = Field(..., ge=0)
    # 评分使用 0-5 区间，便于兼容常见酒店平台。
    rating: float = Field(..., ge=0, le=5)
    # 标签用于说明交通、商圈、亲子、安静等住宿特征。
    tags: list[str] = Field(default_factory=list)
    # 推荐理由和原始证据分开保存，避免把外部原始响应直接混入用户文案。
    reason: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    raw_evidence: str = Field(..., min_length=1)


class HotelResearchSourceStatus(BaseModel):
    """酒店研究来源状态。

    与景点/餐饮候选池类似，酒店候选池也保留来源状态。
    这样 Swagger 验收时可以明确看到“没有酒店候选”是因为来源未接入，而不是节点静默失败。
    """

    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., min_length=1)
    status: Literal["enabled", "not_enabled", "failed"]
    message: str = Field(default="")


class HotelCandidatePool(BaseModel):
    """酒店候选池。

    这是 `hotel_research` 的输出，也是 `hotel_selector` 的输入。
    当前阶段候选通常为空，但结构必须稳定，便于后续接入高德、酒店平台或其它真实来源。
    """

    model_config = ConfigDict(extra="forbid")

    destination: str = Field(..., min_length=1)
    # 记录本次用于搜索的住宿区域名，便于排查酒店候选和路线区域是否匹配。
    recommended_area_names: list[str] = Field(default_factory=list)
    candidates: list[HotelCandidate] = Field(default_factory=list)
    source_status: list[HotelResearchSourceStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HotelSelection(BaseModel):
    """酒店选择结果。

    该结构允许 `selected_hotel` 为空，因为当前阶段外部酒店来源尚未接入。
    这种显式空选择比编造酒店更安全，也能让后续 `verify_plan` 给出明确提示。
    """

    model_config = ConfigDict(extra="forbid")

    selected_hotel: HotelCandidate | None = None
    hotel_reason: str = Field(..., min_length=1)
    backup_hotels: list[HotelCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
