# Architecture Notes

This project is not a fully generic OpenAPI-to-MCP server. It has a reusable
OpenAPI-driven core, but the application is currently packaged and configured
for selected Ex Libris Alma APIs: Acquisitions plus Bibliographic and Inventory.

## Reusable Pieces

- `openapi_catalog.py` parses OpenAPI paths, methods, operation IDs, summaries,
  descriptions, path/query parameters, and request-body metadata.
- `mcp_server.py` generates one MCP tool per parsed operation.
- Tool descriptions and input schemas are derived from the OpenAPI metadata.
- The generic operation-invocation pattern could be reused for another REST API.

## Alma-Specific Pieces

- Configuration uses Alma-specific API key variables such as `ACQ_API_KEY` and
  `BIBS_API_KEY`.
- `AlmaApiClient` authenticates upstream calls by appending Alma's `apikey`
  query parameter.
- Tool names, resource names, docs, Kubernetes resources, and container naming
  are Alma-oriented.
- Tool-name generation strips Alma's `/almaws/v1` path prefix.
- Response metadata preserves Alma's `X-Exl-Api-Remaining` header.
- The bundled OpenAPI documents and docs are for Alma APIs.

## Generic Gaps

Turning this into a general OpenAPI-to-MCP server would require at least:

- Pluggable upstream authentication strategies such as query API key, header API
  key, bearer token, basic auth, and OAuth.
- Support for OpenAPI security schemes.
- Header and cookie parameters.
- OpenAPI parameter serialization styles beyond simple path/query values.
- `$ref` resolution and optional caching for request/response schemas.
- Generated request-body schemas instead of a generic `body` object.
- Multipart/form-data support.
- Configurable API name, tool prefix, path-prefix handling, and base URL/server
  selection.

The dynamic tool generation is the reusable center of the codebase. The current
client, configuration, documentation, and deployment layer are Alma-specific.
