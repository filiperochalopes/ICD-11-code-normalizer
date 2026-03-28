from app.core.config import Settings


def test_settings_normalize_code_normalizer_root_path_from_env(monkeypatch):
    """
    Verify reverse-proxy prefixes are normalized for FastAPI root_path usage.

    Parameters:
    - monkeypatch: Pytest fixture used to control process environment.

    Returns:
    - None.

    Business Rules:
    - Prefixes must gain a leading slash when omitted.
    - Trailing slashes must be removed to avoid duplicate separators in generated URLs.
    """
    monkeypatch.setenv("ROOT_PATH", "code-normalizer-api/")

    settings = Settings(_env_file=None)

    assert settings.code_normalizer_root_path == "/code-normalizer-api"


def test_settings_treat_slash_only_root_path_as_disabled(monkeypatch):
    """
    Ensure a single slash does not force an unnecessary FastAPI root_path prefix.

    Parameters:
    - monkeypatch: Pytest fixture used to control process environment.

    Returns:
    - None.

    Business Rules:
    - A lone slash means the service is already mounted at root.
    - Disabled root_path support must resolve to an empty string.
    """
    monkeypatch.setenv("ROOT_PATH", "/")

    settings = Settings(_env_file=None)

    assert settings.code_normalizer_root_path == ""
