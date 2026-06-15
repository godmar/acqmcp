from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HTTP_METHODS = {"get", "post", "put", "delete", "patch"}
PATH_PARAM_RE = re.compile(r"{([^{}]+)}")
IDENTIFIER_RE = re.compile(r"[^0-9a-zA-Z_]+")


def _clean_identifier(value: str) -> str:
    cleaned = IDENTIFIER_RE.sub("_", value.replace("-", "_")).strip("_")
    if not cleaned:
        return "value"
    if cleaned[0].isdigit():
        return f"_{cleaned}"
    return cleaned


@dataclass(frozen=True)
class Operation:
    operation_id: str
    method: str
    path: str
    tags: tuple[str, ...]
    summary: str
    description: str
    parameters: tuple[dict[str, Any], ...]
    request_body: dict[str, Any] | None
    raw: dict[str, Any]

    @property
    def safe_name(self) -> str:
        return (
            self.operation_id.replace("/", "_")
            .replace("{", "")
            .replace("}", "")
            .replace("-", "_")
        )

    @property
    def tool_name(self) -> str:
        segments = [segment for segment in self.path.strip("/").split("/") if segment]
        if segments[:2] == ["almaws", "v1"]:
            segments = segments[2:]

        name_parts = [self.method]
        for segment in segments:
            match = PATH_PARAM_RE.fullmatch(segment)
            if match:
                name_parts.extend(["by", _clean_identifier(match.group(1))])
            else:
                name_parts.append(_clean_identifier(segment))
        return "_".join(name_parts)

    @property
    def path_parameters(self) -> set[str]:
        return set(PATH_PARAM_RE.findall(self.path))

    @property
    def requires_body(self) -> bool:
        return bool(self.request_body and self.request_body.get("required"))

    def summary_record(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "tool_name": self.tool_name,
            "method": self.method.upper(),
            "path": self.path,
            "tags": list(self.tags),
            "summary": self.summary,
            "description": self.description,
            "path_parameters": sorted(self.path_parameters),
            "query_parameters": [
                {
                    "name": p.get("name"),
                    "required": bool(p.get("required")),
                    "description": p.get("description", ""),
                }
                for p in self.parameters
                if p.get("in") == "query"
            ],
            "has_request_body": self.request_body is not None,
            "requires_request_body": self.requires_body,
        }


class AcqOpenAPICatalog:
    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        self._operations = self._load_operations(spec)

    @classmethod
    def from_file(cls, path: Path) -> "AcqOpenAPICatalog":
        with path.open("r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    @property
    def operations(self) -> dict[str, Operation]:
        return self._operations

    def list_operations(
        self,
        *,
        method: str | None = None,
        tag: str | None = None,
        text: str | None = None,
    ) -> list[dict[str, Any]]:
        method_filter = method.lower() if method else None
        tag_filter = tag.lower() if tag else None
        text_filter = text.lower() if text else None

        records = []
        for operation in self._operations.values():
            if method_filter and operation.method != method_filter:
                continue
            if tag_filter and tag_filter not in {t.lower() for t in operation.tags}:
                continue
            if text_filter:
                haystack = " ".join(
                    [
                        operation.operation_id,
                        operation.path,
                        operation.summary,
                        operation.description,
                        " ".join(operation.tags),
                    ]
                ).lower()
                if text_filter not in haystack:
                    continue
            records.append(operation.summary_record())

        return sorted(records, key=lambda item: (item["path"], item["method"]))

    def get_operation(self, operation_id: str) -> Operation:
        try:
            return self._operations[operation_id]
        except KeyError as exc:
            raise KeyError(f"Unknown operation_id: {operation_id}") from exc

    def render_path(self, operation_id: str, path_params: dict[str, Any] | None) -> str:
        operation = self.get_operation(operation_id)
        provided = path_params or {}
        missing = operation.path_parameters - provided.keys()
        extra = provided.keys() - operation.path_parameters
        if missing:
            raise ValueError(f"Missing path parameters: {sorted(missing)}")
        if extra:
            raise ValueError(f"Unexpected path parameters: {sorted(extra)}")

        path = operation.path
        for name, value in provided.items():
            path = path.replace(f"{{{name}}}", str(value))
        return path

    @staticmethod
    def _load_operations(spec: dict[str, Any]) -> dict[str, Operation]:
        operations: dict[str, Operation] = {}
        for path, path_item in spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            for method, raw_operation in path_item.items():
                if method not in HTTP_METHODS or not isinstance(raw_operation, dict):
                    continue
                operation_id = raw_operation.get("operationId") or f"{method}{path}"
                operations[operation_id] = Operation(
                    operation_id=operation_id,
                    method=method,
                    path=path,
                    tags=tuple(raw_operation.get("tags", [])),
                    summary=raw_operation.get("summary", ""),
                    description=raw_operation.get("description", ""),
                    parameters=tuple(raw_operation.get("parameters", [])),
                    request_body=raw_operation.get("requestBody"),
                    raw=raw_operation,
                )
        return operations
