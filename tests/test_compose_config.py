import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_compose.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="docker CLI not available",
)


def test_docker_compose_config_is_valid() -> None:
    result = subprocess.run(
        [str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
