# SecuraCV Home Assistant integration

The Home Assistant integration for [SecuraCV](https://github.com/kmay89/securaCV) —
privacy-preserving witness infrastructure. It connects Home Assistant to the
**Privacy Witness Kernel** (the signed, hash-chained event log) and to **Canary**
devices, and creates:

- witness event sensors (semantic events — "large object crossed boundary" —
  never footage, never identity),
- a chain-integrity sensor and a **Verify Now** button ("verified" means every
  Ed25519 signature in the chain re-checked against a pinned key — nothing looser),
- a daily-digest sensor,
- the Verified Timeline and Aim Lovelace cards (`www/`).

## Install

### HACS (custom repository, today)

1. HACS → **⋮ → Custom repositories** → add
   `https://github.com/kmay89/securacv-homeassistant` as an **Integration**.
2. Install **SecuraCV**, restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → SecuraCV**.

### The kernel runs separately

The integration talks to a running Privacy Witness Kernel. The easiest way to
run one is the Home Assistant **app** (older Home Assistant calls these
add-ons) from the main repository —
[add the app repository in one click](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkmay89%2FsecuraCV)
— or run it as a Docker container or service. See the
[Home Assistant setup guide](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md).

## Configuration

Everything is a UI config flow — no YAML required. The integration supports
MQTT (Canary devices), the kernel's Event API, or both. For the Event API,
prefer the rotating **token file** (the kernel app writes it to
`/config/api_token`); the integration re-reads it automatically when the token
rotates.

## Development

This repository is the **distribution home** for the integration. The one
distribution-only addition is `custom_components/securacv/brand/` — HACS reads
its icon and logo from there until the `home-assistant/brands` submission is
merged; everything else is byte-identical to the monorepo. Development
currently happens in the main monorepo —
[`kmay89/securaCV`](https://github.com/kmay89/securaCV) under
`custom_components/securacv/` — where the privacy invariants and the
dictionary-sync gate live; changes land there first and are synced here.
Please file issues and PRs against the main repository.

Run the tests standalone:

```sh
pip install -r requirements_test.txt
pytest custom_components/securacv/tests -q
```

## License

[Apache-2.0](LICENSE), same as the main repository.
