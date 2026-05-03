from typing import Protocol

from app.schemas.trip import TripPlanRequest, TripPlanResponse


class TripPlannerLLM(Protocol):
    def generate_plan(self, request: TripPlanRequest) -> TripPlanResponse:
        """Generate a structured trip plan from a validated request."""
