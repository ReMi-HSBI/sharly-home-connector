from functools import wraps
import inspect
import logging
from typing import Any

from pydantic import ValidationError

from .models import EnrollmentResponse, EnrollmentResponsePublic, ProvisionResponse

_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("Importing %s", __file__)


class SharlyService:
    """High-level service layer wrapping the Sharly API."""

    def __init__(self, api) -> None:
        """High-level service layer wrapping the Sharly API.

        Parameters
        ----------
        api : object
            Low-level API client exposing an async ``request(method, url, payload)``
            method.
        """
        self.api = api

    @staticmethod
    def request(method: str, url: str, response_type: Any = None):
        """Decorator factory that maps a method to an HTTP endpoint."""

        def decorator(func):
            sig = inspect.signature(func)

            @wraps(func)
            async def wrapper(self, *args, **kwargs):
                try:
                    bound = sig.bind(self, *args, **kwargs)
                except TypeError:
                    return None

                bound.apply_defaults()
                params = bound.arguments
                path_params = {k: v for k, v in params.items() if "{" + k + "}" in url}
                final_url = url.format(**path_params)

                if inspect.iscoroutinefunction(func):
                    payload = await func(self, *args, **kwargs)
                else:
                    payload = func(self, *args, **kwargs)
                resp = await self.api.request(method, final_url, payload=payload)

                if hasattr(response_type, "model_validate"):
                    try:
                        return response_type.model_validate(resp)
                    except ValidationError as e:
                        raise ValueError(f"Response could not be validated: {e}") from e
                elif hasattr(response_type, "from_dict"):
                    return response_type.from_dict(resp)

                return resp  # fallback if response_type is None

            return wrapper

        return decorator

    @request(method="POST", url="/hubs/enrollments", response_type=EnrollmentResponse)
    async def enroll(self) -> EnrollmentResponse:
        """Create a new home enrollment.

        Returns:
        -------
        EnrollmentResponse
            The created enrollment.
        """
        return None

    @request(
        method="GET",
        url="/hubs/enrollments/{enrollment_id}",
        response_type=EnrollmentResponsePublic,
    )
    async def get_enrollment(self, enrollment_id: int, pairing_code: str) -> dict:
        """Fetch an existing enrollment by ID.

        Parameters
        ----------
        enrollment_id : int
            ID of the enrollment to retrieve.

        Returns:
        -------
        EnrollmentResponsePublic
            Public-facing enrollment data.
        """
        return {
            "pairing_code": pairing_code,
        }

    @request(
        method="POST",
        url="/hubs/enrollments/{enrollment_id}/provision",
        response_type=ProvisionResponse,
    )
    async def provision(
        self, enrollment_id: int, pairing_code: str, node_csr: str
    ) -> dict:
        """Trigger provisioning for an enrollment.

        Parameters
        ----------
        enrollment_id : int
            ID of the enrollment to provision.
        payload : object
            Request body forwarded to the endpoint.

        Returns:
        -------
        ProvisionResponse
            Result of the provisioning request.
        """
        return {"pairing_code": pairing_code, "client_csr": node_csr}
