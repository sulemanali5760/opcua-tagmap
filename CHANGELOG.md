# Changelog

All notable changes to this project are listed here. Versions follow [Semantic Versioning](https://semver.org).

## 0.3.0 - 2026-11-14

- Secured servers: `--security-policy`, `--security-mode`, `--cert-dir`, `--server-cert`, `--user`
  (password from `OPCUA_PASSWORD`). A self-signed client certificate is created on first use.
- `gen telegraf` writes the matching security settings and `password = "${OPCUA_PASSWORD}"`;
  it refuses policies Telegraf cannot speak.

## 0.2.0 - 2026-11-12

- Telegraf output: names that occur more than once get their parent in front (`TIC101_PV`), so the config is valid.
- Browse: member variables of a structured variable are listed; properties of a variable are not.
- README: Telegraf has built-in browse discovery since May 2026; what this tool is still for.
- Releases carry a wheel and offline bundles for Linux and Windows. Python 3.11 or newer.

