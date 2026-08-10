import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

INI_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "app" / "db" / "alembic.ini"
)


def test_alembic_upgrade_head_creates_schema(tmp_path) -> None:
    db_path = tmp_path / "fresh_migration.db"
    code = (
        "from alembic import command; "
        "from alembic.config import Config; "
        f"command.upgrade(Config({str(INI_PATH)!r}), 'head')"
    )
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env.setdefault("JWT_SECRET_KEY", "test-secret-key-test-secret-key-32")

    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == {"alembic_version", "users"}
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        assert version == "0001"
    finally:
        engine.dispose()
