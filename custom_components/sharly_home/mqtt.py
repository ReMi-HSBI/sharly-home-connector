import asyncio
import logging
import ssl
from typing import Any

import aiomqtt

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class SharlyMqttClient:
    def __init__(
        self,
        host: str,
        port: int,
        ca_crt: str | None,
        node_crt: str | None,
        node_key: str | None,
        topic_prefix: str,
    ) -> None:
        self._host = host
        self._port = port
        self._ca_crt = ca_crt
        self._node_crt = node_crt
        self._node_key = node_key
        self._topic_prefix = topic_prefix
        self._client: aiomqtt.Client | None = None
        self._task: asyncio.Task[Any] | None = None
        self._connected_event = asyncio.Event()
        self._stopped = asyncio.Event()

    def start(self, hass: HomeAssistant) -> None:
        if self._task is None or self._task.done():
            self._task = hass.loop.create_task(self._run())

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                _LOGGER.debug("MQTT client task cancelled")

    async def _run(self) -> None:
        ssl_context = None
        if self._ca_crt or self._node_crt or self._node_key:
            ssl_context = ssl.create_default_context(cafile=self._ca_crt)
            if self._node_crt and self._node_key:
                ssl_context.load_cert_chain(
                    certfile=self._node_crt, keyfile=self._node_key, password=None
                )

        while not self._stopped.is_set():
            try:
                async with aiomqtt.Client(
                    hostname=self._host,
                    port=self._port,
                    tls_context=ssl_context,
                ) as client:
                    _LOGGER.info(
                        "Connected to MQTT broker %s:%s", self._host, self._port
                    )
                    self._client = client
                    self._connected_event.set()

                    # Keep the connection open until stopped
                    await self._stopped.wait()
            except aiomqtt.MqttError as err:
                self._client = None
                self._connected_event.clear()
                if self._stopped.is_set():
                    break
                _LOGGER.error("MQTT connection error: %s, retrying in 5s", err)
                await asyncio.sleep(5)

        self._client = None
        self._connected_event.clear()

    async def publish(self, topic_suffix: str, payload: str) -> None:
        await self._connected_event.wait()
        if not self._client:
            _LOGGER.warning("MQTT client not connected, dropping message")
            return

        topic = f"{self._topic_prefix}/{topic_suffix}".lstrip("/")
        try:
            await self._client.publish(
                topic=topic,
                payload=payload.encode("utf-8"),
                qos=1,
                retain=False,
            )
        except aiomqtt.MqttError as err:
            _LOGGER.error("Failed to publish to %s: %s", topic, err)
