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

    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile
    assert "COPY requirements-prod.txt ./" in dockerfile
    assert "COPY --from=builder /install /usr/local" in dockerfile
    assert "USER appuser" in dockerfile
    assert "python -m uvicorn app.main:app" in dockerfile
    assert "${PORT:-8000}" in dockerfile
    assert railway["deploy"]["preDeployCommand"] == "python -m alembic upgrade head"
    assert railway["deploy"]["healthcheckPath"] == "/health"
    assert railway["deploy"]["multiRegionConfig"]["asia-southeast1-eqsg3a"]["numReplicas"] == 1


def test_docker_context_excludes_local_and_generated_files() -> None:
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".git" in ignored
    assert ".env" in ignored
    assert ".env.*" in ignored
    assert ".venv" in ignored
    assert "**/__pycache__" in ignored
    assert "frontend/node_modules" in ignored
    assert "frontend/dist" in ignored


def test_local_compose_services_restart_and_report_readiness() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert services["postgres"]["restart"] == "unless-stopped"
    assert services["postgres"]["healthcheck"]["start_period"] == "10s"
    assert services["redis"]["restart"] == "unless-stopped"
    assert services["redis"]["healthcheck"]["start_period"] == "10s"
    assert "postgres_data" in compose["volumes"]
    assert "volumes" not in services["redis"]


def test_runtime_dependencies_exclude_development_tooling() -> None:
    dev_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    runtime_requirements = (ROOT / "requirements-prod.txt").read_text(encoding="utf-8")

    assert "-r requirements-prod.txt" in dev_requirements
    assert "pytest" not in runtime_requirements
    assert "mypy" not in runtime_requirements
    assert "ruff" not in runtime_requirements
