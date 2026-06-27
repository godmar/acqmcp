# Authentication

All MCP traffic requires a bearer token:

```text
Authorization: Bearer $MCP_BEARER_TOKEN
```

The current implementation uses a pre-shared token verifier that implements the
MCP Python SDK `TokenVerifier` protocol. This keeps the auth boundary in one
place so OAuth2 can replace it later.

The health endpoints `/livez` and `/healthz` are intentionally unauthenticated
so Kubernetes can probe the container.

The server never forwards the MCP bearer token to Ex Libris. Ex Libris API calls
use only `ACQ_API_KEY`, appended as the Alma `apikey` query parameter.

Authorization can later be split by operation because each Alma `operationId`
is exposed as its own MCP tool. The generic `invoke_acq_operation` support tool
should be treated as an administrative fallback if finer-grained authorization
is added.
