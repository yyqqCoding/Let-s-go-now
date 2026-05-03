import pytest
from pydantic import ValidationError

from app.schemas.trip import TravelStyle, TripPlanRequest


def valid_request_data() -> dict:
    return {
        "destination": "杭州",
        "days": 2,
        "budget": 1500,
        "people": 2,
        "preferences": ["自然风景", "本地美食"],
        "avoid": ["太赶", "排队"],
        "travel_style": "relaxed",
    }


def test_trip_plan_request_accepts_valid_data() -> None:
    request = TripPlanRequest(**valid_request_data())

    assert request.destination == "杭州"
    assert request.days == 2
    assert request.budget == 1500
    assert request.people == 2
    assert request.preferences == ["自然风景", "本地美食"]
    assert request.avoid == ["太赶", "排队"]
    assert request.travel_style == TravelStyle.RELAXED


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("days", 0),
        ("people", 0),
        ("budget", 0),
        ("travel_style", "slow"),
        ("preferences", "自然风景"),
        ("avoid", "排队"),
    ],
)
def test_trip_plan_request_rejects_invalid_data(field: str, value: object) -> None:
    data = valid_request_data()
    data[field] = value

    with pytest.raises(ValidationError):
        TripPlanRequest(**data)
