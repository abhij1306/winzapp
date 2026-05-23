import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_local_ci_script_runs_required_checks() -> None:
    script = (ROOT / "scripts" / "local_ci.ps1").read_text(encoding="utf-8")

    assert "docker compose up -d postgres redis" in script
    assert ".\\.venv\\Scripts\\python.exe -m alembic upgrade head" in script
    assert ".\\.venv\\Scripts\\python.exe -m pytest" in script
    assert ".\\.venv\\Scripts\\python.exe -m mypy app" in script
    assert ".\\.venv\\Scripts\\python.exe -m ruff check app tests" in script


def test_github_actions_ci_uses_postgres_redis_and_required_checks() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    rendered = workflow_path.read_text(encoding="utf-8")

    assert "push" in workflow["on"]
    assert "pull_request" in workflow["on"]
    assert "postgres" in workflow["jobs"]["ci"]["services"]
    assert "redis" in workflow["jobs"]["ci"]["services"]
    assert "python -m alembic upgrade head" in rendered
    assert "python -m pytest" in rendered
    assert "python -m mypy app" in rendered
    assert "python -m ruff check app tests" in rendered


def test_dockerfile_and_railway_config_define_single_replica_web_path() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    railway = tomllib.loads((ROOT / "railway.toml").read_text(encoding="utf-8"))

    assert "python -m uvicorn app.main:app" in dockerfile
    assert "${PORT:-8000}" in dockerfile
    assert railway["deploy"]["preDeployCommand"] == "python -m alembic upgrade head"
    assert railway["deploy"]["healthcheckPath"] == "/health"
    assert railway["deploy"]["multiRegionConfig"]["asia-southeast1-eqsg3a"]["numReplicas"] == 1
