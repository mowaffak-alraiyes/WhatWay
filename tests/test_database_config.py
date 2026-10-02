import database


class MissingSecrets:
    def get(self, key, default=None):
        raise FileNotFoundError("no secrets file")


def clear_database_environment(monkeypatch):
    for key in (*database._DATABASE_KEYS, "NEON_SSLMODE"):
        monkeypatch.delenv(key, raising=False)


def test_missing_configuration_is_browser_only_mode(monkeypatch):
    clear_database_environment(monkeypatch)
    monkeypatch.setattr(database.st, "secrets", MissingSecrets())
    monkeypatch.setattr(
        database.psycopg,
        "connect",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not connect")),
    )

    client = database.NeonDatabase()

    assert client.get_connection() is None
    assert client.get_connection() is None
    assert client.unavailable_reason == "not_configured"


def test_environment_configuration_connects_once(monkeypatch):
    clear_database_environment(monkeypatch)
    values = {
        "NEON_DB_HOST": "db.example.test",
        "NEON_DB_NAME": "whatway",
        "NEON_DB_USER": "whatway-app",
        "NEON_PASSWORDLESS_TOKEN": "token-with-special:@chars",
        "NEON_SSLMODE": "verify-full",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    class Connection:
        closed = False

    connection = Connection()
    calls = []

    def fake_connect(**kwargs):
        calls.append(kwargs)
        return connection

    monkeypatch.setattr(database.psycopg, "connect", fake_connect)
    client = database.NeonDatabase()

    assert client.get_connection() is connection
    assert client.get_connection() is connection
    assert len(calls) == 1
    assert calls[0]["password"] == values["NEON_PASSWORDLESS_TOKEN"]
    assert calls[0]["sslmode"] == "verify-full"


def test_failed_connection_is_not_retried_repeatedly(monkeypatch):
    clear_database_environment(monkeypatch)
    for key, value in {
        "NEON_DB_HOST": "db.example.test",
        "NEON_DB_NAME": "whatway",
        "NEON_DB_USER": "whatway-app",
        "NEON_PASSWORDLESS_TOKEN": "token",
    }.items():
        monkeypatch.setenv(key, value)

    attempts = []

    def unavailable(**kwargs):
        attempts.append(kwargs)
        raise OSError("offline")

    monkeypatch.setattr(database.psycopg, "connect", unavailable)
    client = database.NeonDatabase()

    assert client.get_connection() is None
    assert client.get_connection() is None
    assert len(attempts) == 1
    assert client.unavailable_reason == "connection_failed"
