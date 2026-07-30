from ffxi_telemetry.identity import deterministic_event_id


def test_event_identity_is_deterministic_and_position_sensitive():
    raw = b'{"timestamp":"2026-07-30T00:00:00Z"}\n'
    first = deterministic_event_id("runtime/audit/events.jsonl", 1, raw)
    assert first == deterministic_event_id("runtime/audit/events.jsonl", 1, raw)
    assert first != deterministic_event_id("runtime/audit/events.jsonl", 2, raw)
    assert first != deterministic_event_id("runtime/audit/other.jsonl", 1, raw)
