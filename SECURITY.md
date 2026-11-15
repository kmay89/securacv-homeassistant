# Security policy

This repository is the HACS mirror of the SecuraCV Home Assistant
integration. The code under `custom_components/securacv/` is carried
byte-for-byte from [`kmay89/securaCV`](https://github.com/kmay89/securaCV),
where it is developed and where a fix has to land before it can reach here.

## Reporting a vulnerability

Report anything exploitable privately, in the monorepo, not here:

- **[GitHub private vulnerability reporting](https://github.com/kmay89/securaCV/security/advisories/new)**, preferred.
- **errerlabs@gmail.com**, with `security` in the subject, if you would
  rather not use GitHub.

Please do not open a public issue for it, on this repository or that one: a
public issue is a disclosure. This mirror is not a reporting venue of its own.

What to expect back, the disclosure window and which versions are supported
are stated once, in the monorepo's
[`SECURITY.md`](https://github.com/kmay89/securaCV/blob/main/SECURITY.md).
For the integration, the supported version is the newest release of this
repository; a fix arrives as a new release, which HACS offers as an update.
