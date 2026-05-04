import pytest
from pydantic import ValidationError

from app.nodes.merge_candidates import merge_candidate_results
from app.schemas.candidates import CandidatePlace, CandidatePool, PlaceType, ResearchSourceResult
from app.schemas.trip import TripPlanRequest


def test_candidate_place_requires_unified_fields() -> None:
    candidate = CandidatePlace(
        name="西湖",
        type=PlaceType.ATTRACTION,
        source="fallback_llm_research",
        address="杭州市西湖区",
        lat=30.25,
        lng=120.13,
        tags=["自然风景", "城市漫步"],
        reason="符合自然风景偏好，适合轻松游览。",
        estimated_cost=0,
        estimated_duration=180,
        confidence=0.8,
        raw_evidence="真实模型根据用户偏好生成的候选。",
    )

    assert candidate.name == "西湖"
    assert candidate.type == PlaceType.ATTRACTION
    assert candidate.confidence == 0.8


def test_candidate_place_rejects_invalid_type_and_confidence() -> None:
    with pytest.raises(ValidationError):
        CandidatePlace(
            name="错误候选",
            type="shopping",
            source="fallback_llm_research",
            address="杭州",
            lat=None,
            lng=None,
            tags=["购物"],
            reason="不应进入候选池。",
            estimated_cost=0,
            estimated_duration=60,
            confidence=1.5,
            raw_evidence="非法数据。",
        )


def test_merge_candidate_results_splits_types_and_deduplicates_by_confidence() -> None:
    low_confidence = CandidatePlace(
        name="西湖",
        type=PlaceType.ATTRACTION,
        source="fallback_llm_research",
        address="杭州市西湖区",
        lat=30.25,
        lng=120.13,
        tags=["自然风景"],
        reason="低置信度候选。",
        estimated_cost=0,
        estimated_duration=120,
        confidence=0.5,
        raw_evidence="来源 A。",
    )
    high_confidence = low_confidence.model_copy(
        update={
            "source": "amap_poi_research",
            "confidence": 0.9,
            "raw_evidence": "来源 B。",
        }
    )
    food = CandidatePlace(
        name="知味观",
        type=PlaceType.FOOD,
        source="fallback_llm_research",
        address="杭州市上城区",
        lat=30.25,
        lng=120.17,
        tags=["本地美食"],
        reason="符合本地美食偏好。",
        estimated_cost=80,
        estimated_duration=90,
        confidence=0.7,
        raw_evidence="真实模型根据偏好生成。",
    )
    source_results = [
        ResearchSourceResult(source="fallback_llm_research", status="enabled", candidates=[low_confidence, food]),
        ResearchSourceResult(source="amap_poi_research", status="not_enabled", candidates=[high_confidence]),
    ]

    pool = merge_candidate_results(
        request=TripPlanRequest(
            destination="杭州",
            days=2,
            budget=1500,
            people=2,
            preferences=["自然风景", "本地美食"],
            avoid=["排队"],
            travel_style="relaxed",
        ),
        source_results=source_results,
    )

    assert isinstance(pool, CandidatePool)
    assert len(pool.attractions) == 1
    assert pool.attractions[0].confidence == 0.9
    assert pool.attractions[0].source == "amap_poi_research"
    assert len(pool.foods) == 1
    assert pool.foods[0].name == "知味观"
    assert [source.source for source in pool.source_status] == ["fallback_llm_research", "amap_poi_research"]
