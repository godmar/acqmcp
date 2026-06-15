# Local Development

## Configuration

Copy `.env.sample` to `.env` and fill in the real values. Generate
`ACQ_MCP_BEARER_TOKEN` with:

```sh
./make-new-token.sh
```

Required values:

- `ACQ_API_KEY`: Alma API key used by the server when calling Ex Libris.
- `ACQ_BASE_URL`: one of the Ex Libris regional API base URLs.
- `ACQ_MCP_BEARER_TOKEN`: pre-shared bearer token required from MCP clients.
- `ACQ_MCP_URL`: public HTTPS URL for this server.

## Install

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

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
Authorization: Bearer $ACQ_MCP_BEARER_TOKEN
```

The server exposes one concrete MCP tool per configured Alma Acquisitions
`operationId`, plus three support tools:

- `list_acq_operations`
- `get_acq_operation`
- `invoke_acq_operation`

The current server has 59 generated Alma operation tools and 62 total MCP tools.
Agents should prefer the concrete operation tools; the support tools are for
discovery, inspection, and fallback calls.

Tool names are generated from HTTP method and path. For example:

- `GET /almaws/v1/acq/funds` becomes `get_acq_funds`
- `GET /almaws/v1/acq/vendors/{vendorCode}` becomes `get_acq_vendors_by_vendorCode`
- `PUT /almaws/v1/acq/po-lines/{po_line_id}` becomes `put_acq_po_lines_by_po_line_id`

To list the exact tools exposed by a running server:

```sh
python3 - <<'PY'
import asyncio
import os
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    url = os.environ["ACQ_MCP_URL"].rstrip("/")
    if "://" not in url:
        url = "https://" + url
    headers = {"Authorization": "Bearer " + os.environ["ACQ_MCP_BEARER_TOKEN"]}
    async with streamablehttp_client(url + "/mcp", headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            for tool in sorted(tools.tools, key=lambda item: item.name):
                print(tool.name)

asyncio.run(main())
PY
```
