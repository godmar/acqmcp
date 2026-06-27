. .env

case "${MCP_URL}" in
  http://*|https://*) MCP_ENDPOINT="${MCP_URL%/}/mcp" ;;
  *) MCP_ENDPOINT="https://${MCP_URL%/}/mcp" ;;
esac

claude mcp add --transport http alma "${MCP_ENDPOINT}" \
    --header "Authorization: Bearer ${MCP_BEARER_TOKEN}"
