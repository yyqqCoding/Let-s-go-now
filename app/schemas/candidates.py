from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlaceType(StrEnum):
    """候选地点类型。

    当前 V0.3 只区分景点和餐饮两类。
    酒店会在后续 hotel_research / hotel_selector 阶段单独建模，避免候选池职责过宽。
    """

    ATTRACTION = "attraction"
    FOOD = "food"


class CandidatePlace(BaseModel):
    """统一候选地点结构。

    后续无论数据来自小红书、大众点评、高德还是 LLM fallback，都必须先转换成这个结构，
    再进入候选合并和选点节点。
    """

    # 禁止模型或外部来源返回未定义字段，保证后续 merge/select 节点拿到稳定结构。
    model_config = ConfigDict(extra="forbid")

    # 地点展示名。后续去重会基于 name + type，因此这里要求不能为空。
    name: str = Field(..., min_length=1)
    # 候选类型：景点或餐饮。
    type: PlaceType
    # 数据来源标识，例如 fallback_llm_research、amap_poi_research。
    source: str = Field(..., min_length=1)
    # 地址用于人工解释，也为后续接入地图距离计算做准备。
    address: str = Field(..., min_length=1)
    # 经纬度当前允许为空；未接入地图 MCP 前，真实模型可能无法稳定给出坐标。
    lat: float | None = None
    lng: float | None = None
    # 标签用于后续 select_core_places 和用户 preferences 做匹配。
    tags: list[str] = Field(default_factory=list)
    # 入选理由会进入后续行程说明，要求非空。
    reason: str = Field(..., min_length=1)
    # 单人预估费用，单位默认为人民币元；免费景点可为 0。
    estimated_cost: float = Field(..., ge=0)
    # 预计停留时长，单位分钟；route_optimizer 会用它做时间安排。
    estimated_duration: int = Field(..., gt=0, description="预计停留分钟数")
    # 来源可信度，merge 阶段重复候选保留分数更高的一条。
    confidence: float = Field(..., ge=0, le=1)
    # 原始证据或生成依据。真实 MCP 接入后可保存摘要证据，便于排查候选来源。
    raw_evidence: str = Field(..., min_length=1)


class ResearchSourceStatus(BaseModel):
    """单个研究来源的执行状态。

    CandidatePool 只保留状态摘要，不保留各来源的完整中间响应。
    这样 API 调试时能看到哪些来源参与了研究，也避免把外部原始响应直接暴露出去。
    """

    model_config = ConfigDict(extra="forbid")

    # 来源节点名，需要与 app/nodes/research_sources.py 中的函数语义对应。
    source: str = Field(..., min_length=1)
    # enabled 表示已产出或尝试产出候选；not_enabled 表示外部来源暂未接入；failed 表示调用失败。
    status: Literal["enabled", "not_enabled", "failed"]
    # 给 Swagger 和日志看的简短说明，不能承载敏感信息。
    message: str = Field(default="", description="状态说明或失败原因")


class ResearchSourceResult(BaseModel):
    """单个研究来源返回的候选结果。

    research node 内部使用该结构传递候选；merge_candidates 会消费多个 ResearchSourceResult，
    去重后生成最终 CandidatePool。
    """

    model_config = ConfigDict(extra="forbid")

    # 当前来源名。
    source: str = Field(..., min_length=1)
    # 当前来源执行状态。
    status: Literal["enabled", "not_enabled", "failed"]
    # 当前来源返回的原始候选列表，尚未去重。
    candidates: list[CandidatePlace] = Field(default_factory=list)
    # 来源状态说明。
    message: str = Field(default="")

    def to_status(self) -> ResearchSourceStatus:
        """转换为候选池中保留的来源状态。"""

        return ResearchSourceStatus(source=self.source, status=self.status, message=self.message)


class CandidatePool(BaseModel):
    """合并后的候选池。

    这是 V0.3 的核心产物，也是 V0.4 select_core_places 的输入。
    它只回答“有哪些可选地点”，不决定最终去哪些地方。
    """

    model_config = ConfigDict(extra="forbid")

    # 请求目的地，便于后续节点不必反查 request。
    destination: str = Field(..., min_length=1)
    # 用户偏好原样带入，供选点阶段计算匹配度。
    preferences: list[str] = Field(default_factory=list)
    # 用户规避项原样带入，供选点和校验阶段过滤候选。
    avoid: list[str] = Field(default_factory=list)
    # 景点候选，已由 merge_candidates 完成基础去重并按置信度排序。
    attractions: list[CandidatePlace] = Field(default_factory=list)
    # 餐饮候选，已由 merge_candidates 完成基础去重并按置信度排序。
    foods: list[CandidatePlace] = Field(default_factory=list)
    # 各研究来源的状态摘要，用于调试和 Swagger 手工验收。
    source_status: list[ResearchSourceStatus] = Field(default_factory=list)
