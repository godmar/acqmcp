from acqmcp.auth import StaticBearerTokenVerifier


async def test_static_bearer_token_verifier() -> None:
    verifier = StaticBearerTokenVerifier("expected")

    assert await verifier.verify_token("wrong") is None
    token = await verifier.verify_token("expected")

    assert token is not None
    assert token.client_id == "pre-shared-bearer-token"
