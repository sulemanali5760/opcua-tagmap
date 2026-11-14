"""Browse a server that only accepts encrypted sessions with a user login, and emit Telegraf for it."""
import asyncio
import socket
import tomllib

import pytest
from asyncua import Server, ua
from asyncua.crypto import cert_gen
from asyncua.server.user_managers import User, UserManager, UserRole
from cryptography.x509.oid import ExtendedKeyUsageOID

from opcua_tagmap.browse import browse
from opcua_tagmap.emit import telegraf
from opcua_tagmap.model import TagNode
from opcua_tagmap.security import Security

ENDPOINT = "opc.tcp://127.0.0.1:48462/secure/"
USER, PASSWORD = "operator", "s3cret"


class _OneUser(UserManager):
    def get_user(self, iserver, username=None, password=None, certificate=None):
        return User(role=UserRole.User, name=username) if (username, password) == (USER, PASSWORD) else None


async def _serve(pki, ready, stop):
    cert, key = pki / "server_cert.der", pki / "server_key.pem"
    await cert_gen.setup_self_signed_certificate(key, cert, "urn:test:secure", socket.gethostname(),
                                                 [ExtendedKeyUsageOID.SERVER_AUTH], {"commonName": "test"})
    server = Server(user_manager=_OneUser())
    await server.init()
    server.set_endpoint(ENDPOINT)
    await server.set_application_uri("urn:test:secure")
    await server.load_certificate(str(cert))
    await server.load_private_key(str(key))
    server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])
    server.set_identity_tokens([ua.UserNameIdentityToken])
    idx = await server.register_namespace("urn:test:plant")
    plant = await server.nodes.objects.add_object(idx, "Plant")
    await plant.add_variable(idx, "Temperature", 21.5)
    async with server:
        ready.set()
        await stop.wait()


def _browse(tmp_path, security):
    async def run():
        ready, stop = asyncio.Event(), asyncio.Event()
        task = asyncio.create_task(_serve(tmp_path, ready, stop))
        await asyncio.wait_for(ready.wait(), 20)
        try:
            return await browse(ENDPOINT, security=security, timeout=5)
        finally:
            stop.set()
            await task
    return asyncio.run(run())


def _secure(tmp_path, password=PASSWORD):
    return Security("Basic256Sha256", "SignAndEncrypt", str(tmp_path / "client"),
                    str(tmp_path / "server_cert.der"), USER, password)


def test_secured_server_is_browsed_with_certificate_and_login(tmp_path):
    paths = [t.browse_path for t in _browse(tmp_path, _secure(tmp_path)).tags]
    assert paths == ["Objects/Plant/Temperature"]
    assert (tmp_path / "client" / "client_cert.der").exists()       # created on first use


def test_secured_server_refuses_an_anonymous_plain_session(tmp_path):
    with pytest.raises(Exception, match="No matching endpoints"):
        _browse(tmp_path, None)


def test_wrong_password_is_refused(tmp_path):
    with pytest.raises(Exception, match="BadUserAccessDenied"):
        _browse(tmp_path, _secure(tmp_path, password="wrong"))


TAG = [TagNode("Objects/Plant/Temperature", "Temperature", 2, "i", "5", "Double")]


def test_telegraf_config_for_a_secured_server_keeps_the_password_out():
    sec = Security("Basic256Sha256", "SignAndEncrypt", "pki", "server.der", USER, PASSWORD)
    text = telegraf.render(TAG, ENDPOINT, security=sec)
    block = tomllib.loads(text)["inputs"]["opcua"][0]
    assert block["security_policy"] == "Basic256Sha256" and block["security_mode"] == "SignAndEncrypt"
    assert block["auth_method"] == "UserName" and block["username"] == USER
    assert block["password"] == "${OPCUA_PASSWORD}" and PASSWORD not in text


def test_telegraf_refuses_a_policy_it_cannot_speak():
    with pytest.raises(ValueError):
        telegraf.render(TAG, ENDPOINT, security=Security("Aes256_Sha256_RsaPss"))


def test_default_telegraf_config_is_still_anonymous():
    block = tomllib.loads(telegraf.render(TAG, ENDPOINT))["inputs"]["opcua"][0]
    assert block["security_policy"] == "None" and block["auth_method"] == "Anonymous"
