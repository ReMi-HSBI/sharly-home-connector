import asyncio
import json
import logging
from typing import Any

import aiohttp
from pydantic import BaseModel
from yarl import URL

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class SharlyApiClient:
    """Client for communicating with the SHARLY backend API.

    This class is responsible for constructing endpoint URLs and performing
    HTTP requests against the SHARLY service.
    """

    def __init__(self, host: str, port: int | None = None) -> None:
        """Initialize the API client.

        Args:
            host: Hostname or IP of the SHARLY backend (e.g. "host.docker.internal").
            port: Optional port number (e.g. 8000).
        """
        if port is not None:
            self._base = URL(f"{host}:{port}")
        else:
            self._base = URL(f"{host}")

    async def request(
        self,
        method: str,
        url: URL,
        payload: BaseModel | None = None,
    ) -> dict[str, Any]:
        """Perform an HTTP request.

        Args:
            method: HTTP method ("get" or "post").
            url: Target endpoint URL.
            json: Optional JSON payload.

        Returns:
            Parsed JSON response.

        Raises:
            SharlyApiError: If the request fails or returns invalid data.
        """
        url = f"{self._base}{url}"
        _LOGGER.debug("Request: %s %s", method.upper(), url)
        _LOGGER.debug("Payload: %s", payload)

        try:
            async with aiohttp.ClientSession() as session:
                if payload is not None:
                    payload = json.dumps(payload)
                resp = await session.request(
                    method,
                    url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    ssl=False,
                )

                async with resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        raise SharlyApiError(
                            f"Error response from SHARLY API: {resp.status} - {text}"
                        )
                    return await resp.json()
        except aiohttp.ClientResponseError as e:
            _LOGGER.error("Request to %s failed: %s", url, e)
            raise SharlyApiError(e) from e
        except aiohttp.ClientError as e:
            _LOGGER.error("Request to %s failed: %s", url, e)
            raise SharlyApiError(e) from e


class SharlyApiError(HomeAssistantError):
    """Error raised for SHARLY API communication problems."""
