from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_trip_plan_endpoint_returns_structured_plan() -> None:
    response = client.post(
        "/api/trip/plan",
        json={
            "destination": "杭州",
            "days": 2,
            "budget": 1500,
            "people": 2,
            "preferences": ["自然风景", "本地美食"],
            "avoid": ["太赶", "排队"],
            "travel_style": "relaxed",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"]
    assert data["summary"]
    assert data["destination"] == "杭州"
    assert len(data["days"]) == 2
    assert data["budget"]["total_budget"] == 1500
    assert "warnings" in data


def test_trip_plan_endpoint_rejects_invalid_days() -> None:
    response = client.post(
        "/api/trip/plan",
        json={
            "destination": "杭州",
            "days": 0,
            "budget": 1500,
            "people": 2,
            "preferences": ["自然风景"],
            "avoid": [],
            "travel_style": "relaxed",
        },
    )

    assert response.status_code == 422
