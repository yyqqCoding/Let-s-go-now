from pydantic import BaseModel, ConfigDict, Field

from app.schemas.candidates import CandidatePlace


class SelectedPlaces(BaseModel):
    """V0.4 核心地点选择结果。

    CandidatePool 代表“可以选择哪些地点”，SelectedPlaces 代表“本次行程实际优先安排哪些地点”。
    该结构只负责选点结果，不包含路线顺序、每日分组或酒店信息，避免提前侵入 V0.5/V0.6 的职责。
    """

    # 禁止额外字段，确保后续 route_optimizer 消费稳定结构。
    model_config = ConfigDict(extra="forbid")

    # 已选核心景点。数量由 travel_style 和 days 决定。
    selected_attractions: list[CandidatePlace] = Field(default_factory=list)
    # 已选核心餐饮点。当前规则要求尽量不少于 days，保证每天至少有一个正餐候选。
    selected_restaurants: list[CandidatePlace] = Field(default_factory=list)
    # 选择过程说明，便于 Swagger 手工验收和后续排查规则行为。
    selection_notes: list[str] = Field(default_factory=list)
    # 选择过程中的软性问题，例如候选不足、餐饮不足。
    warnings: list[str] = Field(default_factory=list)
