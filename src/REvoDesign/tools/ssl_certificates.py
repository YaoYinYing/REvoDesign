# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
This module contains functions and classes related to managing SSL certificates
and generating unique identifiers (UUIDs).
"""

import datetime
import os
import platform
import secrets
import ssl
from dataclasses import dataclass
from typing import Literal

from OpenSSL import crypto

from REvoDesign.logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


DEFAULT_CERT_VALIDITY_DAYS = 7
CERT_VALIDITY_ENV = "REVODESIGN_SSL_CERT_VALIDITY_DAYS"
PRIVATE_DIR_MODE = 0o700
PRIVATE_KEY_MODE = 0o600
CERTIFICATE_MODE = 0o644


def _certificate_validity_days() -> int:
    raw_days = os.environ.get(CERT_VALIDITY_ENV)
    if raw_days is None:
        return DEFAULT_CERT_VALIDITY_DAYS

    try:
        days = int(raw_days)
    except ValueError as exc:
        raise ValueError(f"{CERT_VALIDITY_ENV} must be a positive integer.") from exc

    if days <= 0:
        raise ValueError(f"{CERT_VALIDITY_ENV} must be a positive integer.")

    return days


def _write_pem_file(path: str, payload: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
    finally:
        os.chmod(path, mode)


@dataclass
class SSLCertificateManager:
    peer_roles = Literal["server", "client"]
    role: peer_roles

    def __post_init__(self):
        from REvoDesign import set_cache_dir

        self.cache_dir: str = set_cache_dir()
        self.crt_dir: str = os.path.join(self.cache_dir, "crts")

        os.makedirs(self.crt_dir, mode=PRIVATE_DIR_MODE, exist_ok=True)
        os.chmod(self.crt_dir, PRIVATE_DIR_MODE)
        self.crt_path = os.path.join(self.crt_dir, f"{self.role}.crt")
        self.key_path = os.path.join(self.crt_dir, f"{self.role}.key")

    def generate_ssl_context(self):
        """
        Generate an SSL context based on the specified role for server or client.

        Args:
        role (str): Role for which the SSL context is generated ('server' or 'client').

        Returns:
        ssl.SSLContext: Generated SSL context.

        Raises:
        ValueError: If an unknown role is provided.
        FileNotFoundError: If client certificate is not found.
        """

        # Generate SSL context and certificate if needed

        self.get_certificate()

        if self.role == "server":
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(self.crt_path, self.key_path)
        elif self.role == "client":
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=self.crt_path)
        else:
            raise ValueError(f"Unknown role of ssl context: {self.role}")
        return context

    def get_certificate(self):
        """
        Function: get_certificate
        Usage: get_certificate()

        This function checks for the existence of an SSL certificate and
        generates a new one if it doesn't exist or has expired.


        Returns:
        - None
        """
        # Check if the existing certificate exists
        if not os.path.exists(self.crt_path):
            logging.info("Certificate does not exist. Generating a new certificate.")
            self.create_new_certificate()
            return

        with open(self.crt_path, "rb") as f:
            existing_cert_data = f.read()
            existing_cert = crypto.load_certificate(crypto.FILETYPE_PEM, existing_cert_data)

            # Get the expiration date of the existing certificate
            expiration_date = datetime.datetime.strptime(existing_cert.get_notAfter().decode("utf-8"), "%Y%m%d%H%M%SZ")

        # Check if the certificate has expired
        if expiration_date < datetime.datetime.now():
            logging.warning("Certificate has expired. Generating a new certificate.")
            self.create_new_certificate()
        else:
            self._enforce_file_permissions()
            logging.info("Certificate is still valid.")

    def create_new_certificate(self):
        """
        Function: create_new_certificate
        Usage: create_new_certificate()

        This function creates a new SSL certificate and private key if they do
        not exist or if the certificate has expired.

        Returns:
        - None
        """
        role = self.role
        validity_days = _certificate_validity_days()

        # Get node information from OS or set to 'Unknown' if not available

        node = platform.node()
        try:
            user = os.getlogin()
        except OSError:
            user = "Unknown"

        # Generate RSA key
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)

        # Create an X.509 certificate
        cert = crypto.X509()
        # Set subject information
        cert.get_subject().C = "CN"
        cert.get_subject().ST = "Yunnan"
        cert.get_subject().L = "Kunming"
        cert.get_subject().O = "JAPS"  # noqa: E741 -- X.509 Organization field
        cert.get_subject().OU = "Yunnan Very Normal University"
        # X.509 CN max 64 chars — truncate hostname if needed
        _cn = f"{user}.{node}.{role}.REvoDesign"
        cert.get_subject().CN = _cn[:64]

        # Set serial number, validity period, issuer, public key, and sign the certificate
        cert.set_serial_number(secrets.randbits(159) + 1)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(validity_days * 24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, "sha256")

        # Write the certificate and private key to files in PEM format
        _write_pem_file(self.crt_path, crypto.dump_certificate(crypto.FILETYPE_PEM, cert), CERTIFICATE_MODE)
        _write_pem_file(self.key_path, crypto.dump_privatekey(crypto.FILETYPE_PEM, k), PRIVATE_KEY_MODE)

    def _enforce_file_permissions(self):
        os.chmod(self.crt_dir, PRIVATE_DIR_MODE)
        if os.path.exists(self.crt_path):
            os.chmod(self.crt_path, CERTIFICATE_MODE)
        if os.path.exists(self.key_path):
            os.chmod(self.key_path, PRIVATE_KEY_MODE)
