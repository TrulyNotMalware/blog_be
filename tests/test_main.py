import pytest
from click.testing import CliRunner

import main as entrypoint
from app.core.config.config import loader


def test_main_bounds_graceful_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    # main() writes ENV and DEBUG into os.environ; setting them here first makes
    # monkeypatch restore them afterwards.
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("DEBUG", "False")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        entrypoint.uvicorn, "run", lambda **kwargs: calls.append(kwargs)
    )

    result = CliRunner().invoke(entrypoint.main, ["--env", "prod"])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    timeout = calls[0]["timeout_graceful_shutdown"]
    assert timeout == loader.config.GRACEFUL_SHUTDOWN_SECONDS
