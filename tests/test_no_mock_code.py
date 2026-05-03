from pathlib import Path


def test_application_code_does_not_contain_mock_llm() -> None:
    scanned_files = [
        path
        for path in Path("app").rglob("*.py")
        if "__pycache__" not in path.parts
    ]

    offenders = [
        str(path)
        for path in scanned_files
        if "MockTripPlannerLLM" in path.read_text(encoding="utf-8")
        or "mock" in path.read_text(encoding="utf-8").lower()
    ]

    assert offenders == []
