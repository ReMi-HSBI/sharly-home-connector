from dataclasses import dataclass, field
import logging

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

_LOGGER = logging.getLogger(__name__)


@dataclass
class CertificateConfig:
    country: str = "DE"
    organization: str = "Hochschule Bielefeld (HSBI)"
    organizational_unit: str = "ReMi"
    common_name: str = "sharly-ha-node"
    uris: list[str] = field(
        default_factory=lambda: [
            "sharly://node/http",
        ]
    )
    dns_names: list[str] = field(
        default_factory=lambda: [
            "sharly-http-node",
            "fb3-sharly.hsbi.de",
            "host.docker.internal",
            "localhost",
            "0.0.0.0",
        ]
    )


class SharlySecurity:
    def __init__(self) -> None:
        self.__client_key: str | None = None
        self.__config = CertificateConfig()

    @property
    def client_key(self) -> str | None:
        if self.__client_key:
            return self.__client_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("utf-8")
        return None

    @property
    def _client_key(self) -> str:
        if self.__client_key:
            return self.__client_key
        self.__client_key = Ed25519PrivateKey.generate()

        return self.__client_key

    def generate_csr(self, home_id: str) -> str:
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, self.__config.country),
                x509.NameAttribute(
                    NameOID.ORGANIZATION_NAME, self.__config.organization
                ),
                x509.NameAttribute(
                    NameOID.ORGANIZATIONAL_UNIT_NAME, self.__config.organizational_unit
                ),
                x509.NameAttribute(NameOID.COMMON_NAME, self.__config.common_name),
            ]
        )

        sans = [x509.UniformResourceIdentifier(home_id)]
        sans.extend(x509.UniformResourceIdentifier(uri) for uri in self.__config.uris)
        sans.extend(x509.DNSName(dns) for dns in self.__config.dns_names)

        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(subject)
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None), critical=True
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False
            )
            .add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .sign(self._client_key, algorithm=None)
        )

        return csr.public_bytes(serialization.Encoding.PEM).decode("utf-8")
