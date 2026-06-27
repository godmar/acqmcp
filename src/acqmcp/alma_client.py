from __future__ import annotations

import json
from typing import Any

import httpx

from acqmcp.openapi_catalog import AcqOpenAPICatalog


class AlmaApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        catalog: AcqOpenAPICatalog,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._catalog = catalog
        self._timeout = timeout
        self._transport = transport

    async def invoke_operation(
        self,
        *,
        operation_id: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        body: Any = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        operation = self._catalog.get_operation(operation_id)
        path = self._catalog.render_path(operation_id, path_params)
        params = {k: v for k, v in (query_params or {}).items() if v is not None}
        params["apikey"] = self._api_key

        headers = {"Accept": "application/json"}
        request_kwargs: dict[str, Any] = {}
        if body is not None:
            headers["Content-Type"] = content_type
            if content_type == "application/json":
                request_kwargs["json"] = body
            else:
                request_kwargs["content"] = body

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.request(
                operation.method.upper(),
                path,
                params=params,
                headers=headers,
                **request_kwargs,
            )

        parsed_body: Any
        response_content_type = response.headers.get("content-type", "")
        if "application/json" in response_content_type:
            parsed_body = response.json()
        else:
            text = response.text
            try:
                parsed_body = json.loads(text)
            except json.JSONDecodeError:
                parsed_body = text

        return {
            "status_code": response.status_code,
            "ok": 200 <= response.status_code < 300,
            "headers": {
                key: value
                for key, value in response.headers.items()
                if key.lower() in {"content-type", "x-exl-api-remaining"}
            },
            "body": parsed_body,
        }


AlmaAcquisitionsClient = AlmaApiClient
