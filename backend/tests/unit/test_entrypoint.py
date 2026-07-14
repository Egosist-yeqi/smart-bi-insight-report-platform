import os
import subprocess
from pathlib import Path


ENTRYPOINT = Path(__file__).parents[2] / "entrypoint.sh"


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)


def _run_entrypoint(tmp_path: Path, alembic_exit_after: int) -> subprocess.CompletedProcess[str]:
    commands = tmp_path / "commands.log"
    attempts = tmp_path / "attempts.txt"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    _write_executable(
        bin_dir / "alembic",
        """#!/bin/sh
count=0
if [ -f \"$ATTEMPT_FILE\" ]; then
    count=$(cat \"$ATTEMPT_FILE\")
fi
count=$((count + 1))
printf '%s' \"$count\" > \"$ATTEMPT_FILE\"
if [ \"$count\" -lt \"$ALEMBIC_SUCCEEDS_ON\" ]; then
    exit 7
fi
""",
    )
    _write_executable(
        bin_dir / "sleep",
        """#!/bin/sh
printf 'sleep:%s\\n' \"$1\" >> \"$COMMAND_LOG\"
""",
    )
    _write_executable(
        bin_dir / "python",
        """#!/bin/sh
printf 'python:%s\\n' \"$*\" >> \"$COMMAND_LOG\"
""",
    )
    _write_executable(
        bin_dir / "uvicorn",
        """#!/bin/sh
printf 'uvicorn:%s\\n' \"$*\" >> \"$COMMAND_LOG\"
""",
    )

    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "ALEMBIC_SUCCEEDS_ON": str(alembic_exit_after),
        "ATTEMPT_FILE": str(attempts),
        "COMMAND_LOG": str(commands),
        "DATABASE_URL": "mysql://test-user:never-log-this-password@mysql/test",
    }
    result = subprocess.run(
        ["/bin/sh", str(ENTRYPOINT)],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=10,
    )
    result.commands = commands.read_text(encoding="utf-8") if commands.exists() else ""
    result.attempts = attempts.read_text(encoding="utf-8") if attempts.exists() else "0"
    return result


def test_entrypoint_retries_migration_before_seeding_and_starting_server(tmp_path):
    result = _run_entrypoint(tmp_path, alembic_exit_after=3)

    assert result.returncode == 0
    assert result.attempts == "3"
    assert result.commands.splitlines() == [
        "sleep:2",
        "sleep:2",
        "python:-m app.db.seed",
        "uvicorn:app.main:create_app --factory --host 0.0.0.0 --port 8000",
    ]
    assert "retrying (1/30)" in result.stderr
    assert "retrying (2/30)" in result.stderr
    assert "never-log-this-password" not in result.stdout
    assert "never-log-this-password" not in result.stderr


def test_entrypoint_fails_after_bounded_migration_retries_without_starting_app(tmp_path):
    result = _run_entrypoint(tmp_path, alembic_exit_after=31)

    assert result.returncode != 0
    assert result.attempts == "30"
    assert result.commands.splitlines() == ["sleep:2"] * 29
    assert "did not succeed after 30 attempts" in result.stderr
    assert "never-log-this-password" not in result.stdout
    assert "never-log-this-password" not in result.stderr
