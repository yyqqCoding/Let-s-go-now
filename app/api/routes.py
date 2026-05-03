from fastapi import APIRouter

from app.graphs.trip_graph import run_trip_graph
from app.schemas.trip import TripPlanRequest, TripPlanResponse

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """服务健康检查接口。"""

    return {"status": "ok"}


@router.post("/api/trip/plan", response_model=TripPlanResponse)
def create_trip_plan(request: TripPlanRequest) -> TripPlanResponse:
    """生成旅游计划。

    FastAPI 负责把请求体校验为 TripPlanRequest，业务流程交给 LangGraph。
    返回值再次受 response_model 约束，确保 Swagger 和客户端看到稳定 JSON。
    """

    return run_trip_graph(request)
