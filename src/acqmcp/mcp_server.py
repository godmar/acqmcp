from __future__ import annotations

import inspect
import keyword
from dataclasses import dataclass
from typing import Annotated, Any

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl, Field

from acqmcp.alma_client import AlmaApiClient
from acqmcp.auth import StaticBearerTokenVerifier
from acqmcp.openapi_catalog import AcqOpenAPICatalog, Operation
from acqmcp.settings import Settings


JSON_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


@dataclass(frozen=True)
class AlmaApiSurface:
    name: str
    display_name: str
    catalog: AcqOpenAPICatalog
    client: AlmaApiClient


def build_mcp_server(
    *,
    settings: Settings,
    api_surfaces: list[AlmaApiSurface],
) -> FastMCP:
    total_operations = sum(len(surface.catalog.operations) for surface in api_surfaces)
    api_summary = ", ".join(
        f"{surface.display_name}: {len(surface.catalog.operations)}" for surface in api_surfaces
    )
    mcp = FastMCP(
        name="Ex Libris Alma",
        instructions=(
            f"This server exposes {total_operations} operation-specific Alma tools "
            f"({api_summary}), plus support tools. Prefer the operation-specific tools "
            "returned by MCP tools/list. Tool names are generated from HTTP method and "
            "path, for example GET /almaws/v1/acq/funds becomes get_acq_funds and GET "
            "/almaws/v1/bibs/{mms_id}/holdings becomes get_bibs_by_mms_id_holdings. "
            "The list_alma_operations, get_alma_operation, and invoke_alma_operation "
            "tools are support tools for discovery, inspection, and fallback calls. "
            "All upstream calls are authenticated by the server with the configured "
            "Alma API key for the selected API."
        ),
        host=settings.host,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        token_verifier=StaticBearerTokenVerifier(settings.mcp_bearer_token),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.public_url),
            resource_server_url=AnyHttpUrl(settings.mcp_endpoint_url),
            required_scopes=[],
        ),
    )

    surfaces_by_name = {surface.name: surface for surface in api_surfaces}

    @mcp.resource("alma://apis/openapi-summary")
    def openapi_summary() -> dict[str, Any]:
        """Return a compact summary of all configured Alma operations."""
        return {
            "operation_count": total_operations,
            "apis": [
                {
                    "name": surface.name,
                    "display_name": surface.display_name,
                    "title": surface.catalog.spec.get("info", {}).get("title"),
                    "version": surface.catalog.spec.get("info", {}).get("version"),
                    "operation_count": len(surface.catalog.operations),
                    "operations": _operation_records(surface),
                }
                for surface in api_surfaces
            ],
        }

    @mcp.tool()
    async def list_alma_operations(
        api: str | None = None,
        method: str | None = None,
        tag: str | None = None,
        text: str | None = None,
    ) -> dict[str, Any]:
        """List supported Alma API operations, optionally filtered."""
        surfaces = _select_surfaces(api_surfaces, api)
        operations = [
            record
            for surface in surfaces
            for record in _operation_records(surface, method=method, tag=tag, text=text)
        ]
        return {"count": len(operations), "operations": operations}

    @mcp.tool()
    async def get_alma_operation(operation_id: str, api: str | None = None) -> dict[str, Any]:
        """Inspect one Alma operation before invoking it."""
        surface, operation = _resolve_operation(api_surfaces, operation_id, api)
        return {
            "api": surface.name,
            "api_display_name": surface.display_name,
            **operation.summary_record(),
            "parameters": list(operation.parameters),
            "request_body": operation.request_body,
            "responses": operation.raw.get("responses", {}),
        }

    @mcp.tool()
    async def invoke_alma_operation(
        operation_id: str,
        api: str | None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        body: Any = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        """Invoke an Alma API operation by operation_id."""
        surface, _ = _resolve_operation(api_surfaces, operation_id, api)
        return await surface.client.invoke_operation(
            operation_id=operation_id,
            path_params=path_params,
            query_params=query_params,
            body=body,
            content_type=content_type,
        )

    _register_operation_tools(mcp=mcp, api_surfaces=api_surfaces)

    return mcp


def _register_operation_tools(
    *,
    mcp: FastMCP,
    api_surfaces: list[AlmaApiSurface],
) -> None:
    seen_names: set[str] = set()
    for surface in api_surfaces:
        for operation in surface.catalog.operations.values():
            if operation.tool_name in seen_names:
                raise ValueError(f"Duplicate MCP tool name generated: {operation.tool_name}")
            seen_names.add(operation.tool_name)

            tool = _build_operation_tool(
                operation_id=operation.operation_id,
                surface=surface,
            )
            mcp.add_tool(
                tool,
                name=operation.tool_name,
                description=_operation_tool_description(operation),
            )


def _build_operation_tool(
    *,
    operation_id: str,
    surface: AlmaApiSurface,
):
    operation = surface.catalog.get_operation(operation_id)
    path_param_names = {
        _tool_argument_name(parameter["name"]): parameter["name"]
        for parameter in operation.parameters
        if parameter.get("in") == "path"
    }
    query_param_names = {
        _tool_argument_name(parameter["name"]): parameter["name"]
        for parameter in operation.parameters
        if parameter.get("in") == "query"
    }
    if len(path_param_names) != len([p for p in operation.parameters if p.get("in") == "path"]):
        raise ValueError(f"Duplicate path argument names generated for {operation.operation_id}")
    if len(query_param_names) != len([p for p in operation.parameters if p.get("in") == "query"]):
        raise ValueError(f"Duplicate query argument names generated for {operation.operation_id}")

    async def operation_tool(**kwargs: Any) -> dict[str, Any]:
        path_params = {
            original_name: kwargs.pop(argument_name)
            for argument_name, original_name in path_param_names.items()
            if argument_name in kwargs
        }
        query_params = {
            original_name: kwargs.pop(argument_name)
            for argument_name, original_name in query_param_names.items()
            if argument_name in kwargs
        }
        body = kwargs.pop("body", None)
        content_type = kwargs.pop("content_type", "application/json")
        if kwargs:
            raise ValueError(f"Unexpected arguments: {sorted(kwargs)}")
        return await surface.client.invoke_operation(
            operation_id=operation_id,
            path_params=path_params,
            query_params=query_params,
            body=body,
            content_type=content_type,
        )

    operation_tool.__name__ = operation.tool_name
    operation_tool.__doc__ = _operation_tool_description(operation)
    operation_tool.__signature__ = _operation_signature(operation)  # type: ignore[attr-defined]
    return operation_tool


def _select_surfaces(api_surfaces: list[AlmaApiSurface], api: str | None) -> list[AlmaApiSurface]:
    if api is None:
        return api_surfaces
    for surface in api_surfaces:
        if surface.name == api:
            return [surface]
    raise ValueError(f"Unknown API: {api}")


def _resolve_operation(
    api_surfaces: list[AlmaApiSurface],
    operation_id: str,
    api: str | None,
) -> tuple[AlmaApiSurface, Operation]:
    matches: list[tuple[AlmaApiSurface, Operation]] = []
    for surface in _select_surfaces(api_surfaces, api):
        if operation_id in surface.catalog.operations:
            matches.append((surface, surface.catalog.get_operation(operation_id)))
    if not matches:
        raise KeyError(f"Unknown operation_id: {operation_id}")
    if len(matches) > 1:
        names = [surface.name for surface, _ in matches]
        raise ValueError(f"operation_id is ambiguous across APIs; provide api. Matches: {names}")
    return matches[0]


def _operation_records(
    surface: AlmaApiSurface,
    *,
    method: str | None = None,
    tag: str | None = None,
    text: str | None = None,
) -> list[dict[str, Any]]:
    return [
        {"api": surface.name, "api_display_name": surface.display_name, **record}
        for record in surface.catalog.list_operations(method=method, tag=tag, text=text)
    ]


def _operation_signature(operation: Operation) -> inspect.Signature:
    required_params: list[inspect.Parameter] = []
    optional_params: list[inspect.Parameter] = []

    for parameter in operation.parameters:
        location = parameter.get("in")
        if location not in {"path", "query"}:
            continue
        name = parameter["name"]
        schema = parameter.get("schema", {})
        annotation = _parameter_annotation(parameter)
        default = inspect.Parameter.empty if parameter.get("required") else schema.get("default", None)
        signature_param = inspect.Parameter(
            name=_tool_argument_name(name),
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=default,
            annotation=annotation,
        )
        if default is inspect.Parameter.empty:
            required_params.append(signature_param)
        else:
            optional_params.append(signature_param)

    if operation.request_body is not None:
        body_param = inspect.Parameter(
            name="body",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=inspect.Parameter.empty if operation.requires_body else None,
            annotation=Annotated[dict[str, Any], Field(description="JSON request body for this Alma operation.")],
        )
        if operation.requires_body:
            required_params.append(body_param)
        else:
            optional_params.append(body_param)
        optional_params.append(
            inspect.Parameter(
                name="content_type",
                kind=inspect.Parameter.KEYWORD_ONLY,
                default="application/json",
                annotation=Annotated[str, Field(description="Request Content-Type header.")],
            )
        )

    return inspect.Signature(
        parameters=[*required_params, *optional_params],
        return_annotation=dict[str, Any],
    )


def _parameter_annotation(parameter: dict[str, Any]) -> Any:
    schema = parameter.get("schema", {})
    python_type = JSON_TYPE_MAP.get(schema.get("type"), Any)
    description = parameter.get("description") or f"{parameter.get('in', 'API')} parameter."
    argument_name = _tool_argument_name(parameter.get("name", ""))
    if argument_name != parameter.get("name"):
        description = f"{description} Original API parameter name: {parameter.get('name')}."
    return Annotated[python_type, Field(description=description)]


def _operation_tool_description(operation: Operation) -> str:
    lines = [operation.summary or operation.tool_name]
    if operation.description:
        lines.extend(["", operation.description])
    return "\n".join(lines)


def _tool_argument_name(name: str) -> str:
    if name.isidentifier() and not keyword.iskeyword(name):
        return name
    candidate = "".join(char if char.isalnum() or char == "_" else "_" for char in name).strip("_")
    if not candidate:
        candidate = "value"
    if candidate[0].isdigit():
        candidate = f"_{candidate}"
    if keyword.iskeyword(candidate):
        candidate = f"{candidate}_"
    return candidate
