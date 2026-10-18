# -*- coding: utf-8 -*-
"""config.py: Control_Center/.env is loaded once, by every entry point,
before anything reads the environment. The real .env is never read here
(tests/conftest.py sets CONTROL_CENTER_NO_DOTENV=1); these tests use a
temporary file."""

import re
import sys
from pathlib import Path

import pytest  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config                                             # noqa: E402

PAGES = ["13_", "14_", "15_", "19_", "20_", "21_", "22_", "23_", "24_"]


def _lines(path: Path) -> list[str]:
    return path.read_bytes().decode("utf-8").splitlines()


def _first(lines, pattern) -> int:
    rx = re.compile(pattern)
    return next((i for i, l in enumerate(lines) if rx.match(l)), 10 ** 6)


def test_config_module_exists():
    assert (ROOT / "config.py").is_file()
    assert config.ROOT == ROOT
    assert config._ENV_PATH == ROOT / ".env"
    assert callable(config.env_status) and callable(config.load_env_file)
    assert isinstance(config._LOADED, bool)


def test_config_loads_env_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_bytes(b"CC_TEST_ALPHA=from-file\nCC_TEST_BETA=file-beta\n")
    monkeypatch.delenv("CC_TEST_ALPHA", raising=False)
    monkeypatch.setenv("CC_TEST_BETA", "already-set")
    assert config.load_env_file(env) is True
    import os
    assert os.environ["CC_TEST_ALPHA"] == "from-file"
    assert os.environ["CC_TEST_BETA"] == "already-set"      # env wins
    assert config.load_env_file(tmp_path / "missing.env") is False
    # the import-time loader reads <ROOT>/.env unless tests opt out
    other = tmp_path / "second"
    other.mkdir()
    (other / ".env").write_bytes(b"CC_TEST_GAMMA=gamma\n")
    monkeypatch.delenv("CC_TEST_GAMMA", raising=False)
    monkeypatch.setattr(config, "_ENV_PATH", other / ".env")
    monkeypatch.setattr(config, "_ENV_LOCAL_PATH", other / ".env.local")
    monkeypatch.setenv("CONTROL_CENTER_NO_DOTENV", "1")
    assert config._load_once() is False and "CC_TEST_GAMMA" not in os.environ
    monkeypatch.delenv("CONTROL_CENTER_NO_DOTENV")
    assert config._load_once() is True
    assert os.environ["CC_TEST_GAMMA"] == "gamma"
    monkeypatch.delenv("CC_TEST_ALPHA", raising=False)
    monkeypatch.delenv("CC_TEST_GAMMA", raising=False)


def test_env_status_returns_all_required_keys(monkeypatch):
    keys = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
            "SMTP_FROM", "WHATSAPP_PHONE_ID", "WHATSAPP_TOKEN",
            "SERPER_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    status = config.env_status()
    assert list(status) == keys
    assert status == dict.fromkeys(keys, False)
    monkeypatch.setenv("SMTP_HOST", "smtp.secret-host.example")
    monkeypatch.setenv("SERPER_API_KEY", "")                # empty = missing
    status = config.env_status()
    assert status["SMTP_HOST"] is True and status["SERPER_API_KEY"] is False
    assert all(isinstance(v, bool) for v in status.values())
    assert "secret-host" not in repr(status)                # names only


def test_app_imports_config():
    lines = _lines(ROOT / "app.py")
    cfg = _first(lines, r"import config\b")
    assert cfg < _first(lines, r"import streamlit")
    assert cfg < _first(lines, r"from ui_common")
    assert cfg < _first(lines, r"(import|from) (pandas|datetime)")
    # ui_common imports config for .env loading
    ui = (ROOT / "ui_common.py").read_text(encoding="utf-8")
    assert re.search(r"^import config\b", ui, re.M)
    # env status is shown on the Settings page
    settings_page = (ROOT / "pages" / "11_⚙️_Settings.py"
                     ).read_text(encoding="utf-8")
    assert "config.env_status()" in settings_page
    assert re.search(r"^import config\b", (ROOT / "atlas_services" /
                                           "__init__.py").read_text(
        encoding="utf-8"), re.M)


def test_scheduler_imports_config(monkeypatch, capsys):
    lines = _lines(ROOT / "scheduler" / "run_daily.py")
    cfg = _first(lines, r"import config\b")
    assert cfg < _first(lines, r"import argparse")
    assert cfg < _first(lines, r"from atlas_services")
    assert re.search(r"^import config\b", (ROOT / "scheduler" /
                                           "__init__.py").read_text(
        encoding="utf-8"), re.M)
    from scheduler import run_daily as RD
    calls = []
    monkeypatch.setattr(RD, "run_daily", lambda **kw: calls.append(kw) or {
        "result": "ok"})
    # missing SMTP / Serper: a real run stops before doing anything
    monkeypatch.setattr(config, "env_status", lambda: {
        "SMTP_HOST": False, "SMTP_PASSWORD": False, "SERPER_API_KEY": True,
        "TELEGRAM_BOT_TOKEN": False})
    assert RD.main([]) == 2 and calls == []
    out = capsys.readouterr().out
    assert "STOPPED: missing critical env vars: ['SMTP_HOST', " \
        "'SMTP_PASSWORD']" in out
    # a dry run needs neither, so it still runs
    assert RD.main(["--dry-run"]) == 0 and calls[-1]["dry_run"] is True
    # everything present: a real run goes ahead
    monkeypatch.setattr(config, "env_status", lambda: {"SMTP_HOST": True,
                                                       "SERPER_API_KEY": True})
    assert RD.main([]) == 0 and calls[-1]["dry_run"] is False


def test_all_pages_import_config():
    for prefix in PAGES:
        page = next((ROOT / "pages").glob(prefix + "*.py"))
        lines = _lines(page)
        cfg = _first(lines, r"import config\b")
        assert cfg < 10 ** 6, page.name
        assert _first(lines, r"sys\.path\.insert") < cfg  # path set first
        assert cfg < _first(lines, r"import streamlit"), page.name
    # every other page loads it through ui_common
    for other in (ROOT / "pages").glob("*.py"):
        src = other.read_text(encoding="utf-8")
        assert "import config" in src or "from ui_common" in src, other.name
