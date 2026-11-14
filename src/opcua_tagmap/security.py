"""How to reach a secured server: secure channel, client certificate, user login.

The password never comes from the command line (it would sit in the shell history and the
process list); it is read from the environment variable OPCUA_PASSWORD.
"""

import os
import pathlib
import socket
import sys
from dataclasses import dataclass

from asyncua import Client, ua
from asyncua.crypto import cert_gen, security_policies
from cryptography.x509.oid import ExtendedKeyUsageOID

APP_URI = "urn:opcua-tagmap:client"
POLICIES = ("None", "Basic256Sha256", "Aes128_Sha256_RsaOaep", "Aes256_Sha256_RsaPss")
MODES = ("Sign", "SignAndEncrypt")
PASSWORD_ENV = "OPCUA_PASSWORD"


@dataclass(frozen=True)
class Security:
    policy: str = "None"
    mode: str = "SignAndEncrypt"
    cert_dir: str = "pki"
    server_cert: str | None = None
    username: str | None = None
    password: str | None = None

    @property
    def secure_channel(self) -> bool:
        return self.policy != "None"

    @property
    def client_cert(self) -> pathlib.Path:
        return pathlib.Path(self.cert_dir) / "client_cert.der"

    @property
    def client_key(self) -> pathlib.Path:
        return pathlib.Path(self.cert_dir) / "client_key.pem"


def from_args(args) -> Security:
    password = None
    if args.user:
        password = os.environ.get(PASSWORD_ENV)
        if password is None:
            sys.exit(f"error: --user given but {PASSWORD_ENV} is not set")
    return Security(args.security_policy, args.security_mode, args.cert_dir,
                    args.server_cert, args.user, password)


async def apply(client: Client, sec: Security) -> None:
    """Configure `client` for `sec`. Creates a self-signed client certificate on first use."""
    if sec.secure_channel:
        if sec.policy not in POLICIES:
            raise ValueError(f"unsupported security policy {sec.policy!r}")
        if not sec.client_cert.exists():
            sec.client_cert.parent.mkdir(parents=True, exist_ok=True)
            await cert_gen.setup_self_signed_certificate(
                sec.client_key, sec.client_cert, APP_URI, socket.gethostname(),
                [ExtendedKeyUsageOID.CLIENT_AUTH],
                {"organizationName": "opcua-tagmap", "commonName": "opcua-tagmap client"})
            print(f"created {sec.client_cert}: the server must trust this certificate "
                  "before it accepts the connection", file=sys.stderr)
        if sec.server_cert is None:
            print("warning: no --server-cert given, so the server's identity is not checked",
                  file=sys.stderr)
        client.application_uri = APP_URI
        await client.set_security(
            getattr(security_policies, f"SecurityPolicy{sec.policy}"),
            str(sec.client_cert), str(sec.client_key),
            server_certificate=sec.server_cert,
            mode=getattr(ua.MessageSecurityMode, sec.mode))
    if sec.username:
        client.set_user(sec.username)
        client.set_password(sec.password)
