from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TravelStyle(StrEnum):
    RELAXED = "relaxed"
    BALANCED = "balanced"
    INTENSIVE = "intensive"


class BudgetLevel(StrEnum):
    """预算等级。

    V0.8.1 开始，预算节点会根据“人均每天预算”给出粗略等级。
    该等级用于解释预算压力，后续 verify_plan / repair_plan 会继续消费。
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Activity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_period: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    place: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    estimated_cost: float = Field(..., ge=0)
    tips: str = Field(..., min_length=1)


class DayPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: int = Field(..., ge=1)
    theme: str = Field(..., min_length=1)
    activities: list[Activity] = Field(..., min_length=1)


class BudgetBreakdown(BaseModel):
    """预算拆分。

    所有金额单位默认是人民币元。字段提供默认值，是为了兼容真实模型旧结构输出；
    进入 `estimate_budget` 后会被规则化估算覆盖。
    """

    model_config = ConfigDict(extra="forbid")

    accommodation: float = Field(default=0, ge=0)
    food: float = Field(default=0, ge=0)
    transport: float = Field(default=0, ge=0)
    tickets: float = Field(default=0, ge=0)
    other: float = Field(default=0, ge=0)


class BudgetEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_budget: float = Field(..., gt=0)
    estimated_total_cost: float = Field(..., ge=0)
    currency: str = Field(default="CNY", min_length=1)
    notes: str = Field(..., min_length=1)
    # 预算拆分由 estimate_budget 生成；默认值用于兼容旧模型输出和旧测试构造。
    breakdown: BudgetBreakdown = Field(default_factory=BudgetBreakdown)
    # 默认 medium，estimate_budget 会按 request 重新计算。
    level: BudgetLevel = BudgetLevel.MEDIUM


class TripPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(..., min_length=1)
    days: int = Field(..., ge=1)
    budget: float = Field(..., gt=0, description="整个行程的总预算")
    people: int = Field(..., ge=1)
    preferences: list[str] = Field(..., min_length=1)
    avoid: list[str] = Field(default_factory=list)
    travel_style: TravelStyle


class TripPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    days: list[DayPlan] = Field(..., min_length=1)
    budget: BudgetEstimate
    warnings: list[str] = Field(default_factory=list)
