from hmac import compare_digest

from mcp.server.auth.provider import AccessToken, TokenVerifier


class StaticBearerTokenVerifier(TokenVerifier):
    """Validate the pre-shared bearer token from configuration.

    The class implements the SDK TokenVerifier protocol so OAuth2 resource-server
    auth can replace this later without changing the MCP tool layer.
    """

    def __init__(self, expected_token: str) -> None:
        self._expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not compare_digest(token, self._expected_token):
            return None
        return AccessToken(
            token=token,
            client_id="pre-shared-bearer-token",
            scopes=["acq:read", "acq:write"],
            subject="configured-token",
        )
