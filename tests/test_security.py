import subprocess


def test_model_config_file_is_ignored_by_git() -> None:
    result = subprocess.run(["git", "check-ignore", "model_config.toml"], capture_output=True, text=True)

    assert result.returncode == 0
    assert result.stdout.strip() == "model_config.toml"


def test_model_config_file_is_not_tracked_by_git() -> None:
    result = subprocess.run(["git", "ls-files", "--error-unmatch", "model_config.toml"], capture_output=True, text=True)

    assert result.returncode != 0
