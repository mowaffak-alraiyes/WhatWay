from api.rate_limit import allow
from core.privacy import hash_identifier, mask_phone, truncate_user_text


def test_mask_phone_keeps_last_four():
    masked = mask_phone("whatsapp:+12167035113")
    assert masked.endswith("5113")
    assert "216703" not in masked


def test_hash_stable():
    assert hash_identifier("+15551212") == hash_identifier("+15551212")
    assert len(hash_identifier("x", length=16)) == 16


def test_truncate():
    assert len(truncate_user_text("a" * 5000, 100)) == 100


def test_rate_limit_blocks():
    key = "test-rate-" + hash_identifier("unit")
    for _ in range(3):
        ok, _ = allow(key, per_minute=3, scope="unit")
        assert ok
    ok, retry = allow(key, per_minute=3, scope="unit")
    assert not ok
    assert retry >= 1
