from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
import ssl
import tempfile
from typing import Any

from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)
_LOGGER.debug(__file__)


@dataclasses.dataclass(frozen=True)
class TLSParameters:
    ca_certs: str | None = None
    certfile: str | None = None
    keyfile: str | None = None
    cert_reqs: ssl.VerifyMode | None = None
    tls_version: Any | None = None
    ciphers: str | None = None
    keyfile_password: str | None = None


async def build_tls_params(
    entry: ConfigEntry | dict[str, str | int | ssl.VerifyMode],
) -> tuple[TLSParameters, list[str]]:
    """Build TLS parameters from a config entry or raw dict, writing certs to temp files.

    Parameters
    ----------
    entry : ConfigEntry or dict of {str : str or int or ssl.VerifyMode}
        TLS configuration source. Must contain ``ca_certs``, ``certfile``,
        ``keyfile``, and ``cert_reqs``.

    Returns:
    -------
    tls_params : TLSParameters
        Constructed TLS parameter object referencing the temp file paths.
    tmp_paths : list of str
        Paths of the created temp files; caller is responsible for cleanup.
    """
    if isinstance(entry, ConfigEntry):
        data = entry.data
    else:
        data = entry

    _ca_certs_data = data.get("ca_certs")
    _certfile_data = data.get("certfile")
    _keyfile_data = data.get("keyfile")
    _cert_reqs = data.get("cert_reqs")

    # Write cert content to temp files; delete=False so the path stays valid
    # after close. This is required because raw PEM strings are not supported.
    ca_cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    certfile_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    keyfile_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")

    try:
        ca_cert_file.write(
            _ca_certs_data.encode()
            if isinstance(_ca_certs_data, str)
            else _ca_certs_data
        )
        certfile_file.write(
            _certfile_data.encode()
            if isinstance(_certfile_data, str)
            else _certfile_data
        )
        keyfile_file.write(
            _keyfile_data.encode() if isinstance(_keyfile_data, str) else _keyfile_data
        )
    finally:
        ca_cert_file.close()
        certfile_file.close()
        keyfile_file.close()

    return TLSParameters(
        ca_certs=ca_cert_file.name,
        certfile=certfile_file.name,
        keyfile=keyfile_file.name,
        cert_reqs=_cert_reqs,
    ), [
        ca_cert_file.name,
        certfile_file.name,
        keyfile_file.name,
    ]  # return paths for cleanup


async def remove_temp_files(tmp_files: dict[str]) -> None:
    """Delete temporary files from the filesystem.

    Parameters
    ----------
    tmp_files : dict of str
        Iterable of file paths to remove. Missing files are silently ignored.
    """
    for path in tmp_files:
        Path(path).unlink(missing_ok=True)
