from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from .const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_TOPIC_PREFIX


@dataclass
class Enrollment:
    """Helper container for the config_flow process."""

    state: str | None = None
    task: asyncio.Task | None = None
    enrollment_id: str | None = None
    home_id: str | None = None
    pairing_code: str | None = None
    expires_at: str | None = None


@dataclass
class HomeContainer:
    """Home Container containing all relevant information for the final setup."""

    mqtt_host: str = DEFAULT_HOST
    mqtt_port: int = DEFAULT_PORT
    topic_prefix: str = DEFAULT_TOPIC_PREFIX
    cert_paths: CertificatePaths = None


@dataclass(frozen=True)
class CertificatePaths:
    """Information about certificates."""

    ca_crt: Path
    node_crt: Path
    node_key: Path


@dataclass
class EnrollmentResponse:
    """Information about a home enrollment to read."""

    enrollment_id: str | None = None
    pairing_code: str | None = None
    expires_at: str | None = None


@dataclass
class EnrollmentResponsePublic:
    """Information about a home enrollment to read publicly."""

    home_id: str | None = None
    expires_at: str | None = None


@dataclass
class ProvisionRequest:
    """Information about a home enrollment to provision."""

    pairing_code: str = None
    node_csr: str = None


@dataclass
class ProvisionResponse:
    """Information about a provisioned home enrollment."""

    mqtt_host: str | None = None
    mqtt_port: int | None = None
    node_crt: str | None = None
    ca_crt: str | None = None
