"""Tests for the opt-in audit logging boundary (issue #121)."""

import json
import logging
from datetime import datetime, timezone

import pytest

from mcp_zammad.audit import AuditConfig, AuditConfigError, AuditLogger, redact

FIXED_TIME = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)


def _fixed_clock() -> datetime:
    return FIXED_TIME


def _stderr_logger(**overrides: str) -> AuditLogger:
    env = {"ZAMMAD_AUDIT_LOG_ENABLED": "true", "ZAMMAD_AUDIT_LOG_DESTINATION": "stderr", **overrides}
    return AuditLogger(AuditConfig.from_env(env), now=_fixed_clock)


def _records(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_config_defaults_to_disabled() -> None:
    config = AuditConfig.from_env({})
    assert config.enabled is False


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_config_enabled_truthy_values(value: str) -> None:
    config = AuditConfig.from_env({"ZAMMAD_AUDIT_LOG_ENABLED": value})
    assert config.enabled is True
    assert config.destination == "stderr"


def test_config_rejects_unknown_destination() -> None:
    env = {"ZAMMAD_AUDIT_LOG_ENABLED": "true", "ZAMMAD_AUDIT_LOG_DESTINATION": "elasticsearch"}
    with pytest.raises(AuditConfigError, match="ZAMMAD_AUDIT_LOG_DESTINATION"):
        AuditConfig.from_env(env)


def test_config_file_destination_requires_path() -> None:
    env = {"ZAMMAD_AUDIT_LOG_ENABLED": "true", "ZAMMAD_AUDIT_LOG_DESTINATION": "file"}
    with pytest.raises(AuditConfigError, match="ZAMMAD_AUDIT_LOG_FILE"):
        AuditConfig.from_env(env)


def test_config_ignores_destination_when_disabled() -> None:
    config = AuditConfig.from_env({"ZAMMAD_AUDIT_LOG_DESTINATION": "bogus"})
    assert config.enabled is False


def test_disabled_logger_emits_nothing(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    file_path = tmp_path / "audit.jsonl"
    env = {"ZAMMAD_AUDIT_LOG_DESTINATION": "file", "ZAMMAD_AUDIT_LOG_FILE": str(file_path)}
    audit = AuditLogger(AuditConfig.from_env(env))

    audit.log_event("tool_call", "zammad_get_ticket", success=True)

    assert audit.enabled is False
    assert not file_path.exists()
    assert capsys.readouterr() == ("", "")
    assert logging.getLogger("zammad.audit").handlers == []


def test_stderr_sink_writes_json_lines_never_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    audit = _stderr_logger()

    audit.log_event(
        "tool_call",
        "zammad_get_ticket",
        success=True,
        resource_type="ticket",
        resource_id=42,
        duration_ms=12.5,
        details={"page": 1},
    )

    out, err = capsys.readouterr()
    assert out == ""
    assert _records(err) == [
        {
            "timestamp": "2026-09-08T12:00:00+00:00",
            "event_type": "tool_call",
            "action": "zammad_get_ticket",
            "success": True,
            "resource_type": "ticket",
            "resource_id": 42,
            "duration_ms": 12.5,
            "details": {"page": 1},
        }
    ]


def test_file_sink_appends_json_lines(tmp_path) -> None:
    file_path = tmp_path / "nested" / "audit.jsonl"
    env = {"ZAMMAD_AUDIT_LOG_DESTINATION": "file", "ZAMMAD_AUDIT_LOG_FILE": str(file_path)}
    audit = _stderr_logger(**env)

    audit.log_event("tool_call", "first", success=True)
    audit.log_event("tool_call", "second", success=False)

    actions = [record["action"] for record in _records(file_path.read_text())]
    assert actions == ["first", "second"]


def test_syslog_sink_uses_syslog_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[str] = []

    class FakeSysLogHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            emitted.append(self.format(record))

    monkeypatch.setattr("mcp_zammad.audit.SysLogHandler", FakeSysLogHandler)
    audit = _stderr_logger(ZAMMAD_AUDIT_LOG_DESTINATION="syslog")

    audit.log_event("security_validation", "url_check", success=False)

    assert [json.loads(line)["event_type"] for line in emitted] == ["security_validation"]


def test_reconfiguration_does_not_duplicate_handlers(capsys: pytest.CaptureFixture[str]) -> None:
    _stderr_logger()
    audit = _stderr_logger()

    audit.log_event("tool_call", "once", success=True)

    assert len(_records(capsys.readouterr().err)) == 1


def test_details_are_redacted_before_serialization(capsys: pytest.CaptureFixture[str]) -> None:
    audit = _stderr_logger()
    details = {
        "password": "hunter2",
        "nested": {"http_token": "abc123", "keep": "visible"},
        "headers": [{"Authorization": "Bearer xyz"}],
        "attachment": {"data": "aGVsbG8="},
    }

    audit.log_event("authentication", "login", success=True, details=details)

    err = capsys.readouterr().err
    for secret in ("hunter2", "abc123", "Bearer xyz", "aGVsbG8="):
        assert secret not in err
    record = _records(err)[0]
    assert record["details"]["nested"]["keep"] == "visible"
    assert record["details"]["password"] == "[REDACTED]"


def test_redact_is_pure_and_case_insensitive() -> None:
    original = {"SECRET_KEY": "s", "list": [{"api_token": "t"}, "plain"], "ok": 1}

    result = redact(original)

    assert result == {"SECRET_KEY": "[REDACTED]", "list": [{"api_token": "[REDACTED]"}, "plain"], "ok": 1}
    assert original["SECRET_KEY"] == "s"
