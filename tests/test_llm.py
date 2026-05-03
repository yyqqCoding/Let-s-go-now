import pytest

from app.core.config import Settings
from app.core.model_config import get_llm_provider, get_openai_model_config
from app.llm.openai_compatible import OpenAICompatibleTripPlannerLLM
from app.schemas.trip import TripPlanRequest


def test_openai_compatible_llm_requires_api_key(tmp_path) -> None:
    model_config_file = tmp_path / "model_config.toml"
    model_config_file.write_text(
        """[llm]
provider = "openai_compatible"

[openai.default]
api_key = ""
base_url = "https://example.test/v1"
model = "test-model"
temperature = 0

[openai.nodes.generate_plan]
api_key = ""
base_url = ""
model = ""
temperature = 0
""",
        encoding="utf-8",
    )
    settings = Settings(MODEL_CONFIG_FILE=str(model_config_file))
    request = TripPlanRequest(
        destination="杭州",
        days=2,
        budget=1500,
        people=2,
        preferences=["自然风景", "本地美食"],
        avoid=["太赶", "排队"],
        travel_style="relaxed",
    )

    llm = OpenAICompatibleTripPlannerLLM(settings)

    with pytest.raises(ValueError, match="api_key"):
        llm.generate_plan(request)


def test_model_config_file_controls_provider_and_node_config(tmp_path) -> None:
    model_config_file = tmp_path / "model_config.toml"
    model_config_file.write_text(
        """[llm]
provider = "openai_compatible"

[openai.default]
api_key = "global-key"
base_url = "https://global.example/v1"
model = "global-model"
temperature = 0

[openai.nodes.generate_plan]
api_key = "node-key"
base_url = "https://node.example/v1"
model = "node-model"
temperature = 0.3
""",
        encoding="utf-8",
    )
    settings = Settings(MODEL_CONFIG_FILE=str(model_config_file))

    config = get_openai_model_config(settings, "generate_plan")

    assert get_llm_provider(settings) == "openai_compatible"
    assert config.model == "node-model"
    assert config.api_key == "node-key"
    assert config.base_url == "https://node.example/v1"
    assert config.temperature == 0.3


def test_openai_compatible_llm_generates_real_structured_plan() -> None:
    settings = Settings()
    request = TripPlanRequest(
        destination="杭州",
        days=2,
        budget=1500,
        people=2,
        preferences=["自然风景", "本地美食"],
        avoid=["太赶", "排队"],
        travel_style="relaxed",
    )

    plan = OpenAICompatibleTripPlannerLLM(settings).generate_plan(request)

    assert plan.destination == "杭州"
    assert len(plan.days) == 2
    assert plan.title
    assert plan.summary
    assert plan.budget.total_budget > 0
