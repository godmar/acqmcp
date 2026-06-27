# Local Development

## Configuration

Copy `.env.sample` to `.env` and fill in the real values. Generate
`MCP_BEARER_TOKEN` with:

```sh
./make-new-token.sh
```

Required values:

- `ACQ_API_KEY`: Alma API key used for Acquisitions API calls.
- `BIBS_API_KEY`: Alma API key used for Bibliographic and Inventory API calls.
- `API_BASE_URL`: one of the Ex Libris regional API base URLs.
- `MCP_BEARER_TOKEN`: pre-shared bearer token required from MCP clients.
- `MCP_URL`: public HTTPS URL for this server.

## Install

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

See `docs/architecture.md` for notes on which parts of this server are reusable
OpenAPI-to-MCP plumbing and which parts are specific to Alma APIs.

## Test

```sh
pytest
```

## Run

```sh
uvicorn acqmcp.main:app --host 0.0.0.0 --port 8000 --reload
```

Health checks are available at `/livez` and `/healthz`. The MCP streamable HTTP
endpoint is `/mcp` and requires:

```text
Authorization: Bearer $MCP_BEARER_TOKEN
```

The server exposes one concrete MCP tool per configured Alma `operationId`,
plus three support tools:

- `list_alma_operations`
- `get_alma_operation`
- `invoke_alma_operation`

The current server has 59 Acquisitions operation tools, 77 Bibliographic and
Inventory operation tools, and 139 total MCP tools. Agents should prefer the
concrete operation tools; the support tools are for discovery, inspection, and
fallback calls.

Tool names are generated from HTTP method and path. For example:

- `GET /almaws/v1/acq/funds` becomes `get_acq_funds`
- `GET /almaws/v1/acq/vendors/{vendorCode}` becomes `get_acq_vendors_by_vendorCode`
- `GET /almaws/v1/bibs/{mms_id}/holdings` becomes `get_bibs_by_mms_id_holdings`

To list the exact tools exposed by a running server:

```sh
python3 - <<'PY'
import asyncio
import os
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    url = os.environ["MCP_URL"].rstrip("/")
    if "://" not in url:
        url = "https://" + url
    headers = {"Authorization": "Bearer " + os.environ["MCP_BEARER_TOKEN"]}
    async with streamablehttp_client(url + "/mcp", headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            for tool in sorted(tools.tools, key=lambda item: item.name):
                print(tool.name)

asyncio.run(main())
PY
```
