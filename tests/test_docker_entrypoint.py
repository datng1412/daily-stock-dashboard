import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_docker_entrypoint_has_valid_shell_syntax() -> None:
    if shutil.which("sh") is None:
        pytest.skip("sh is not available on this host")

    subprocess.run(
        ["sh", "-n", str(REPO_ROOT / "docker" / "entrypoint.sh")],
        check=True,
    )


def test_dockerfile_runs_entrypoint_and_application_as_non_root_user() -> None:
    dockerfile = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "ENV PYTHONUNBUFFERED=1" in dockerfile
    assert "HOME=/home/dsa" in dockerfile
    assert "/home/dsa/.longbridge" in dockerfile
    assert "chown -R dsa:dsa /app /home/dsa" in dockerfile
    assert "chmod 700 /home/dsa/.longbridge" in dockerfile
    assert 'ENTRYPOINT ["/entrypoint.sh"]' in dockerfile
    assert "USER dsa" in dockerfile
    assert "chmod 777" not in dockerfile


def test_dockerfile_bundles_mozyfin_cli_for_vietnam_dashboard() -> None:
    dockerfile = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "mozyfin-cli-builder" not in dockerfile
    assert "npm install -g mozyfin-cli" not in dockerfile
    assert "/usr/local/bin/mozyfin-cli" not in dockerfile


def test_requirements_include_only_official_ssi_v3_sdk_for_docker_runtime() -> None:
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert re.search(r"(?m)^ssi-sdk==3\.0\.5(?:\s+#.*)?$", requirements)
    assert "ssi-fc-data" not in requirements


def test_docker_entrypoint_requires_writable_runtime_directories() -> None:
    entrypoint = (REPO_ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")

    assert "DATA_CACHE_DIR" in entrypoint
    assert "/app/data/cache" in entrypoint
    assert '"$HOME/.longbridge"' in entrypoint
    assert 'HOME="${HOME:-/home/dsa}"' in entrypoint
    assert "assert_writable_dir" in entrypoint
    assert ".dsa-write-check.$$" in entrypoint
    assert 'exec "$@"' in entrypoint
    assert "gosu" not in entrypoint
    assert "sudo" not in entrypoint
    assert "chmod 777" not in entrypoint


def test_docker_compose_injects_env_without_single_file_env_mount() -> None:
    compose_text = (REPO_ROOT / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    compose = yaml.safe_load(compose_text)
    service = compose["services"]["vietnam-dashboard"]

    assert service["build"]["context"] == ".."
    assert service["build"]["dockerfile"] == "docker/Dockerfile"
    assert service["environment"]["DATA_CACHE_DIR"] == "/app/data/cache"
    assert "../.env:/app/.env" not in service["volumes"]
    assert not any(str(volume).startswith("../.env:") for volume in service["volumes"])
    assert "../data:/app/data" in service["volumes"]


def test_docker_guides_do_not_recommend_single_file_env_bind_mount() -> None:
    forbidden_mount_patterns = [
        r"\$\(pwd\)/\.env:/app/\.env",
        r"\.\./\.env:/app/\.env",
    ]

    for doc_path in ("docs/full-guide.md", "docs/full-guide_EN.md"):
        doc = (REPO_ROOT / doc_path).read_text(encoding="utf-8")

        assert "--env-file .env" in doc
        assert "env_file:" in doc
        for pattern in forbidden_mount_patterns:
            assert re.search(pattern, doc) is None


def test_documented_compose_exec_commands_run_as_dsa() -> None:
    safe_exec_prefix = "docker-compose -f ./docker/docker-compose.yml exec -u dsa"
    unsafe_exec_prefix = "docker-compose -f ./docker/docker-compose.yml exec"

    for doc_path in ("docs/DEPLOY.md", "docs/DEPLOY_EN.md"):
        doc = (REPO_ROOT / doc_path).read_text(encoding="utf-8")

        assert f"{safe_exec_prefix} stock-analyzer bash" in doc
        assert f"{safe_exec_prefix} stock-analyzer python main.py --no-notify" in doc
        assert f"{unsafe_exec_prefix} stock-analyzer bash" not in doc
        assert (
            f"{unsafe_exec_prefix} stock-analyzer python main.py --no-notify"
            not in doc
        )


def test_entrypoint_fails_with_bounded_path_only_message_for_unwritable_home(tmp_path: Path) -> None:
    if shutil.which("sh") is None:
        pytest.skip("sh is not available on this host")

    non_directory_home = tmp_path / "home-file"
    non_directory_home.write_text("not a directory", encoding="utf-8")
    result = subprocess.run(
        ["sh", str(REPO_ROOT / "docker" / "entrypoint.sh"), "true"],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(non_directory_home), "DATA_CACHE_DIR": str(tmp_path / "cache")},
    )

    assert result.returncode != 0
    assert result.stderr.startswith("ERROR: required runtime directory")
    assert "Authorization" not in result.stderr
