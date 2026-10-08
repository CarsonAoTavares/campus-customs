from __future__ import annotations

import fcntl
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(__file__).resolve().parents[1] / 'output' / 'audit_trail.json'
_write_lock = threading.Lock()


def _short(value: Any, limit: int = 180) -> Any:
    if isinstance(value, str):
        clipped = value[:limit]
        clipped = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[redacted-email]', clipped)
        return re.sub(r'(?i)(password|api[_ -]?key|token)\s*[:=]\s*\S+', r'\1=[redacted]', clipped)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _short(item, 80) for key, item in list(value.items())[:8]}
    if isinstance(value, (list, tuple)):
        return [_short(item, 80) for item in list(value)[:8]]
    if hasattr(value, 'model_dump'):
        return _short(value.model_dump(mode='json'), limit)
    return str(value)[:limit]


def append_audit_event(
    tool_name: str,
    arguments: dict[str, Any],
    result: Any,
    stop_reason: str | None = None,
) -> None:
    event = {
        'time': datetime.now(timezone.utc).isoformat(),
        'tool_name': tool_name,
        'arguments': _short(arguments),
        'result': _short(result),
        'stop_reason': stop_reason,
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock, AUDIT_PATH.open('a+', encoding='utf-8') as log:
        fcntl.flock(log.fileno(), fcntl.LOCK_EX)
        log.seek(0)
        try:
            events = json.load(log)
            if not isinstance(events, list):
                events = []
        except (json.JSONDecodeError, OSError):
            events = []
        events.append(event)
        log.seek(0)
        log.truncate()
        json.dump(events, log, ensure_ascii=True, indent=2)
        log.write('\n')
        log.flush()
        os.fsync(log.fileno())
        fcntl.flock(log.fileno(), fcntl.LOCK_UN)