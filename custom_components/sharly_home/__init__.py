"""The SHARLY integration."""

from __future__ import annotations

import json
import logging

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
from .mqtt import SharlyMqttClient
from .utils import extract_location

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SHARLY from a config entry."""
    _LOGGER.debug("SHARLY Setup Entry")
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

    mqtt_client = SharlyMqttClient(
        host=_host,
        port=_port,
        ca_crt=_ca_crt,
        node_crt=_node_crt,
        node_key=_node_key,
        topic_prefix=_topic_prefix,
    )
    mqtt_client.start(hass)

    async def handle_state_change(event: Event[EventStateChangedData]) -> None:
        new_state = event.data.get("new_state")
        if not new_state:
            return

        entity_id = event.data.get("entity_id")
        if not entity_id:
            return

        attributes = dict(new_state.attributes)

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
            _LOGGER.warning("Failed to serialize payload for %s", entity_id)
            return

        _LOGGER.debug("Payload: %s", payload)

        topic_suffix = f"{sensor_type}/{entity_id.split('.')[1]}"
        await mqtt_client.publish(topic_suffix, message)

    _LOGGER.debug("Store data in hass storage")

    remove_listener = hass.bus.async_listen(EVENT_STATE_CHANGED, handle_state_change)
    hass.data[DOMAIN][entry.entry_id] = {
        "host": _host,
        "port": _port,
        "ca_crt": _ca_crt,
        "node_crt": _node_crt,
        "node_key": _node_key,
        "topic_prefix": _topic_prefix,
        "event_listener": remove_listener,
        "mqtt_client": mqtt_client,
    }

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unload SHARLY configuration")
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    mqtt_client: SharlyMqttClient | None = entry_data.get("mqtt_client")
    if mqtt_client:
        await mqtt_client.stop()

    # hass.bus.async_listen(...) returns a callable "remove listener" function.
    # It is not the listener itself; it’s a function which must be called to unsubscribe.
    event_listener = entry_data.get("event_listener")
    if callable(event_listener):
        event_listener()

    hass.data[DOMAIN].pop(entry.entry_id, None)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload configuration when changed via UI."""
    _LOGGER.debug("Reloading SHARLY configuration")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
