"""The SHARLY integration."""

from __future__ import annotations

import sys

sys.path.insert(
    0,
    "config/custom_components/sharly_home/aiomqtt",
)

sys.path.insert(
    0,
    "config/custom_components/sharly_home/core/src",
)
import asyncio
import json
import logging
import traceback
from typing import TYPE_CHECKING

import aiomqtt
from google.protobuf.wrappers_pb2 import StringValue

_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("Importing %s", __file__)
_LOGGER.debug("Import stack:\n%s", "".join(traceback.format_stack(limit=10)))
_LOGGER.debug(aiomqtt.__file__)

if TYPE_CHECKING:
    try:
        import sharly
    except ImportError as e:
        _LOGGER.critical("Importing SHARLY failed: %s", e)

try:
    import sharly
except ImportError as e:
    _LOGGER.critical("Importing SHARLY failed: %s", e)


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import EventStateChangedData

from .const import (
    CONF_TOPIC_PREFIX,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TOPIC_PREFIX,
    DOMAIN,
)
from .utils import extract_location


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SHARLY from a config entry."""
    _LOGGER.debug("SHARLY Setup Entry.")
    hass.data.setdefault(DOMAIN, {})

    # Load required information either after the inital setup
    # or after a restart. We need to load all information here upfront
    # to be able to store them atleast once after the setup, to ensure data
    # doesn't get lost.
    _host = entry.data.get("host", DEFAULT_HOST)
    _port = entry.data.get("port", DEFAULT_PORT)
    _ca_crt = entry.data.get("ca_crt")
    _node_crt = entry.data.get("node_crt")
    _node_key = entry.data.get("node_key")
    _topic_prefix = entry.data.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX)

    # TODO(d.dening): Generate password for node key?
    config = sharly.Config(
        mqtt_host=_host,
        mqtt_port=_port,
        ca_crt_path=_ca_crt,
        node_crt_path=_node_crt,
        node_key_path=_node_key,
        node_key_password=None,
    )

    node = sharly.Node(config)
    node_task = hass.loop.create_task(node.run())

    async def handle_state_change(event: Event[EventStateChangedData]) -> None:
        new_state = event.data.get("new_state")
        if not new_state:
            return

        entity_id = event.data.get("entity_id")
        if not entity_id:
            return

        attributes = dict(new_state.attributes)
        sensor_type = None
        location = None

        try:
            sensor_type = new_state.attributes.get("device_class", None)
        except (AttributeError, IndexError, TypeError) as e:
            _LOGGER.warning("Failed to extract sensor_type for %s: %s", entity_id, e)
            return

        if sensor_type is None:
            sensor_type = "unknown"

        try:
            location = await extract_location(entity_id.split(".")[1])
        except (AttributeError, TypeError) as e:
            _LOGGER.warning("Failed to extract location for %s: %s", entity_id, e)
            location = None

        payload = {
            "id": entity_id,
            "timestamp": new_state.last_updated.isoformat(),
            "state": new_state.state,
            "sensor_type": sensor_type,
            "location": location,
            "attributes": attributes,
        }

        try:
            message = json.dumps(payload)
        except TypeError:
            return

        _LOGGER.debug("Payload: %s", payload)

        try:
            async with sharly.Node(config) as node:
                await node.publish(
                    topic=f"{sharly.Topic.EVENTS}/{sensor_type}/{entity_id.split('.')[1]}",
                    packet=StringValue(value=message),
                    qos=aiomqtt.QoS.AT_LEAST_ONCE,
                    retain=False,
                )
        except aiomqtt.ConnectError as e:
            _LOGGER.error(e)

    _LOGGER.debug("Store data in hass storage.")
    hass.data[DOMAIN][entry.entry_id] = {
        "host": _host,
        "port": _port,
        "ca_crt": _ca_crt,
        "node_crt": _node_crt,
        "node_key": _node_key,
        "topic_prefix": _topic_prefix,
        "event_listener": hass.bus.async_listen(
            EVENT_STATE_CHANGED, handle_state_change
        ),
        "node_task": node_task,
    }

    return True


# TODO(d.dening): Fix failed unloading, sharly.Node not stopping?
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    node_task = entry_data.get("node_task")
    if node_task:
        node_task.cancel()
        try:
            await node_task
        except asyncio.CancelledError:
            _LOGGER.debug("Node task cancelled")

    # hass.bus.async_listen(...) returns a callable "remove listener" function.
    # It is not the listener itself; it’s a function which must be called to unsubscribe.
    event_listener = entry_data.get("event_listener")
    if callable(event_listener):
        event_listener()

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload configuration when changed via UI."""
    _LOGGER.debug("Reloading SHARLY configuration")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
