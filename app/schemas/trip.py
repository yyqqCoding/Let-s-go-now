from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TravelStyle(StrEnum):
    RELAXED = "relaxed"
    BALANCED = "balanced"
    INTENSIVE = "intensive"


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


class BudgetEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_budget: float = Field(..., gt=0)
    estimated_total_cost: float = Field(..., ge=0)
    currency: str = Field(default="CNY", min_length=1)
    notes: str = Field(..., min_length=1)


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
