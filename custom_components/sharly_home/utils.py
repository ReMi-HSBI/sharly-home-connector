import logging
import re

_LOGGER = logging.getLogger(__name__)

locations = ["bathroom", "bedroom", "corridor", "kitchen", "livingroom"]
escaped_locations = [re.escape(loc) for loc in locations]
location_pattern = f"({'|'.join(escaped_locations)})"


async def extract_location(sensor_name: str) -> str | None:
    """Attempts to extract the room/location from the sensor name.

    Parameters:
    ----------
    sensor_name : str
        The name of the sensor.

    Returns:
    -------
    str
        The extracted location (e.g., 'bedroom', 'kitchen'), or None if no match is found.
    """
    match = re.search(
        location_pattern,
        sensor_name,
        re.IGNORECASE,
    )

    return match.group(1) if match else None
