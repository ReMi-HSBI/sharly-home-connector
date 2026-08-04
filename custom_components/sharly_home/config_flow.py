"""Config flow for the SHARLY integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import logging
from pathlib import Path
import traceback
from typing import Any

from dateutil.parser import isoparse
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .api import SharlyApiClient, SharlyApiError
from .const import (
    CONF_HTTP_PORT,
    CONF_HTTP_SERVER,
    CONF_TOPIC_PREFIX,
    DEFAULT_HTTP_PORT,
    DEFAULT_HTTP_SERVER,
    DOMAIN,
)
from .models import (
    CertificatePaths,
    Enrollment,
    EnrollmentResponsePublic,
    HomeContainer,
)
from .security import SharlySecurity
from .service import SharlyService

_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("Importing %s", __file__)
_LOGGER.debug("Import stack:\n%s", "".join(traceback.format_stack(limit=10)))

CERT_DIR = "sharly_home/certificates"


class SharlyHomeFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SHARLY."""

    VERSION = 1
    TIMEOUT: int = 30

    def __init__(self) -> None:
        """Init."""
        self.http_server: str = DEFAULT_HTTP_SERVER
        self.http_port: int = DEFAULT_HTTP_PORT
        self.client: SharlyApiClient = None
        self.service: SharlyService = None
        self.security: SharlySecurity = SharlySecurity()
        self.enrollment: Enrollment = Enrollment()
        self.home: HomeContainer = HomeContainer()

    # TODO(dimitri.dening): This step is only used to speedup debug sessions
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step debug."""
        errors: dict[str, str] = {}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HTTP_SERVER, default=DEFAULT_HTTP_SERVER): str,
                vol.Optional(CONF_HTTP_PORT, default=DEFAULT_HTTP_PORT): int,
            }
        )

        if user_input is not None:
            try:
                validated_data = data_schema(user_input)
                self.http_server = validated_data[CONF_HTTP_SERVER]
                self.http_port = validated_data[CONF_HTTP_PORT]
            except vol.Invalid as e:
                errors["base"] = str(e)

            self.client = SharlyApiClient(self.http_server, self.http_port)
            self.service = SharlyService(self.client)

            return await self.async_step_qr()

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    # ***********************************
    # _STEP_: QR CODE;
    # Begin enrollment process;
    # Use response to generate QR code;
    # ***********************************
    async def async_step_qr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step scan."""
        errors: dict[str, str] = {}

        if user_input is None:
            try:
                data = await self.service.enroll()
            except SharlyApiError:
                return self.async_abort(reason="cannot_connect")
            except ValueError as e:
                _LOGGER.error(e)
                return self.async_abort(reason="qr_data_value")

            _LOGGER.debug("Enrollment: %s", data)

            self.enrollment.enrollment_id = data.get("enrollment_id")
            self.enrollment.pairing_code = data.get("pairing_code")
            self.enrollment.expires_at = data.get("expires_at")
            qr_code = json.dumps(data)
            expires_at_dt = None
            expires_at_time = None

            try:
                expires_at_dt = isoparse(self.enrollment.expires_at)
                if expires_at_dt.tzinfo is None:
                    expires_at_dt = expires_at_dt.replace(tzinfo=dt_util.UTC)
                local_dt = dt_util.as_local(expires_at_dt)
                expires_at_time = local_dt.strftime("%H:%M")
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Failed to parse expires_at '%s': %s", self.enrollment.expires_at, e
                )

            return self.async_show_form(
                step_id="qr",
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): selector.QrCodeSelector(
                            config=selector.QrCodeSelectorConfig(
                                data=qr_code,
                                scale=5,
                                error_correction_level=selector.QrErrorCorrectionLevel.QUARTILE,
                            )
                        )
                    }
                ),
                errors=errors,
                description_placeholders={
                    "expires_at": expires_at_time,
                },
            )

        return await self.async_step_enroll()

    # ***********************************
    # _STEP_: ENROLL/CLAIM_POLLING;
    # Use polling to check for enrollment state;
    # ***********************************
    async def _poll_enrollment(
        self, enrollment_id: str, pairing_code: str
    ) -> EnrollmentResponsePublic:
        deadline = dt_util.utcnow() + timedelta(seconds=self.TIMEOUT)
        while dt_util.utcnow() < deadline:
            result = await self.service.get_enrollment(enrollment_id, pairing_code)
            hub_id = result.get("hub_id")
            if hub_id:
                return hub_id
            await asyncio.sleep(1)
        raise TimeoutError

    async def async_step_enroll(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step enroll."""
        if self.enrollment.task is None:
            self.enrollment.task = self.hass.async_create_task(
                self._poll_enrollment(
                    self.enrollment.enrollment_id, self.enrollment.pairing_code
                )
            )

        if not self.enrollment.task.done():
            return self.async_show_progress(
                step_id="enroll",
                progress_action="enrolling",
                progress_task=self.enrollment.task,
            )

        try:
            hub_id = self.enrollment.task.result()
        except (SharlyApiError, ValueError) as e:
            _LOGGER.error(e)
            self.enrollment.state = "enroll_failed"
            return self.async_show_progress_done(next_step_id="failed")
        except TimeoutError as e:
            _LOGGER.error(e)
            self.enrollment.state = "timeout"
            return self.async_show_progress_done(next_step_id="failed")

        self.enrollment.home_id = hub_id
        self.enrollment.state = "qr_claimed"
        return self.async_show_progress_done(next_step_id="provision")

    async def async_step_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step failed."""
        return self.async_abort(reason=self.enrollment.state)

    # ***********************************
    # _STEP_: PROVISION/CERTS;
    # Generate certificates with provision data;
    # ***********************************
    async def write_certs_to_disk(
        self, ca_crt: str, node_crt: str, node_key: str
    ) -> CertificatePaths:
        cert_dir = Path(self.hass.config.config_dir) / CERT_DIR
        cert_dir.mkdir(parents=True, exist_ok=True)

        ca_crt_path = cert_dir / "ca.crt"
        node_crt_path = cert_dir / "node.crt"
        node_key_path = cert_dir / "node.key"

        ca_crt_path.write_text(ca_crt)
        node_crt_path.write_text(node_crt)
        node_key_path.write_text(node_key)

        return CertificatePaths(
            ca_crt=ca_crt_path,
            node_crt=node_crt_path,
            node_key=node_key_path,
        )

    async def async_step_provision(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step cert."""
        try:
            node_csr = self.security.generate_csr(self.enrollment.home_id)
        except ValueError as e:
            _LOGGER.error(e)
            return self.async_abort(reason="cert_generation_error")

        try:
            data = await self.service.provision(
                self.enrollment.enrollment_id, self.enrollment.pairing_code, node_csr
            )
        except SharlyApiError as e:
            _LOGGER.error(e)
            return self.async_abort(reason="cannot_connect")
        except ValueError as e:
            _LOGGER.error(e)
            return self.async_abort(reason="cert_data_error")

        _cert_paths = await self.write_certs_to_disk(
            data.get("ca_crt"), data.get("node_crt"), self.security.client_key
        )

        _LOGGER.debug("CA certificate: %s", _cert_paths.ca_crt)
        _LOGGER.debug("Node certificate: %s", _cert_paths.node_crt)
        _LOGGER.debug("Node key: %s", _cert_paths.node_key)

        self.home.mqtt_host = data.get("mqtt_host")
        self.home.mqtt_port = data.get("mqtt_port")
        self.home.cert_paths = _cert_paths

        return await self.async_step_broker()

    # ***********************************
    # _STEP_: BROKER;
    # Deprecated; Remove later;
    # ***********************************
    async def async_step_broker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step broker."""
        errors: dict[str, str] = {}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self.home.mqtt_host): str,
                vol.Required(CONF_PORT, default=self.home.mqtt_port): int,
                vol.Required(CONF_TOPIC_PREFIX, default=self.home.topic_prefix): str,
            }
        )

        if user_input is not None:
            try:
                validated_data = data_schema(user_input)
                self.home.mqtt_host = validated_data[CONF_HOST]
                self.home.mqtt_port = validated_data[CONF_PORT]
                self.home.topic_prefix = validated_data[CONF_TOPIC_PREFIX]
            except vol.Invalid as e:
                errors["base"] = str(e)
            else:
                return await self.async_step_finish()

        return self.async_show_form(
            step_id="broker", data_schema=data_schema, errors=errors
        )

    # ***********************************
    # _STEP_: FINISH;
    # Finalize integration setup;
    # ***********************************
    async def _test_connection(self) -> str | bool:
        """Return an error key, or True on success."""
        # TODO: Re-write connection test with sharly.Node(..)
        # return "cannot_connect"
        # return "cannot_connect"
        # return "unknown"
        return True

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle final step."""
        errors: dict[str, str] = {}

        data = {
            "host": self.home.mqtt_host,
            "port": self.home.mqtt_port,
            "ca_crt": self.home.cert_paths.ca_crt,
            "node_crt": self.home.cert_paths.node_crt,
            "node_key": self.home.cert_paths.node_key,
        }

        error = await self._test_connection()

        if not error:
            errors["base"] = error
        else:
            return self.async_create_entry(title="SHARLY", data=data)
        return self.async_abort(reason=error)
