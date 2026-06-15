#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import shlex
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
GENERATED = ROOT / "k8s" / "generated"

CONFIG_KEYS = {
    "ACQ_BASE_URL",
    "ACQ_MCP_URL",
    "LOG_LEVEL",
    "PORT",
    "ACQ_REQUEST_TIMEOUT_SECONDS",
}
SECRET_KEYS = {
    "ACQ_API_KEY",
    "ACQ_MCP_BEARER_TOKEN",
}


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value:
            try:
                value = shlex.split(value)[0]
            except ValueError:
                value = value.strip("'\"")
        values[key] = value
    return values


def write_env_file(path: Path, values: dict[str, str], keys: set[str]) -> None:
    lines = [f"{key}={values[key]}" for key in sorted(keys) if values.get(key)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_docker_config(path: Path, values: dict[str, str]) -> None:
    server = values.get("REGISTRY_SERVER")
    username = values.get("REGISTRY_USERNAME")
    password = values.get("REGISTRY_PASSWORD")
    if not all([server, username, password]):
        path.write_text('{"auths":{}}\n', encoding="utf-8")
        return
    auth = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    path.write_text(
        json.dumps({"auths": {server: {"username": username, "password": password, "auth": auth}}}),
        encoding="utf-8",
    )


def write_image_patch(path: Path, values: dict[str, str]) -> None:
    image = values.get("ACQ_MCP_IMAGE", "acq-mcp:local")
    path.write_text(
        "\n".join(
            [
                "apiVersion: apps/v1",
                "kind: Deployment",
                "metadata:",
                "  name: acq-mcp",
                "spec:",
                "  template:",
                "    spec:",
                "      containers:",
                "        - name: acq-mcp",
                f"          image: {image}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_ingress_patch(path: Path, values: dict[str, str]) -> None:
    public_url = values["ACQ_MCP_URL"]
    if "://" not in public_url:
        public_url = f"https://{public_url}"
    parsed = urlparse(public_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SystemExit("ACQ_MCP_URL must be an https URL with a host")
    service_path = parsed.path.rstrip("/") or "/"
    path.write_text(
        "\n".join(
            [
                "apiVersion: networking.k8s.io/v1",
                "kind: Ingress",
                "metadata:",
                "  name: acq-mcp",
                "spec:",
                "  rules:",
                f"    - host: {parsed.hostname}",
                "      http:",
                "        paths:",
                f"          - path: {service_path}",
                "            pathType: Prefix",
                "            backend:",
                "              service:",
                "                name: acq-mcp",
                "                port:",
                "                  number: 80",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    if not ENV_PATH.exists():
        raise SystemExit(".env does not exist")
    values = parse_env(ENV_PATH)
    required_keys = {"ACQ_API_KEY", "ACQ_BASE_URL", "ACQ_MCP_BEARER_TOKEN", "ACQ_MCP_URL"}
    missing = sorted(required_keys - values.keys())
    if missing:
        raise SystemExit(f".env is missing required keys: {', '.join(missing)}")

    GENERATED.mkdir(parents=True, exist_ok=True)
    write_env_file(GENERATED / "config.env", values, CONFIG_KEYS)
    write_env_file(GENERATED / "secret.env", values, SECRET_KEYS)
    write_docker_config(GENERATED / "dockerconfigjson", values)
    write_image_patch(GENERATED / "deployment-image-patch.yaml", values)
    write_ingress_patch(GENERATED / "ingress-patch.yaml", values)
    print(f"Wrote generated Kubernetes inputs to {GENERATED}")


if __name__ == "__main__":
    main()
