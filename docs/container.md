# Container

Build locally:

```sh
docker build -t acq-mcp:local .
```

Run locally with your `.env`:

```sh
docker run --rm --env-file .env -p 8000:8000 acq-mcp:local
```

If you publish to a registry, set `MCP_IMAGE` in `.env` to the full image
reference you want Kubernetes to run.

Then build and push that exact reference:

```sh
docker build -t "$MCP_IMAGE" .
docker push "$MCP_IMAGE"
```
