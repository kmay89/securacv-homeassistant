# SecuraCV Home Assistant integration

**Witnessing without watching.** The Home Assistant integration for
[SecuraCV](https://github.com/kmay89/securaCV) — a local-first witness layer
that records **what happened** as signed, verifiable events, never footage and
never identity. It connects Home Assistant to **Canary** witness devices and
to the **Privacy Witness Kernel** (the signed, hash-chained event log), and
creates:

- witness event sensors (semantic events — "large object crossed boundary" —
  never footage, never identity),
- chain-integrity and daily-digest sensors ("verified" means every Ed25519
  signature in the chain re-checked against a pinned key — nothing looser;
  the kernel app's MQTT discovery adds a **Verify Now** button beside them),
- the Verified Timeline and Aim Lovelace cards (`www/`), registered as
  dashboard resources automatically.

Two entities you may have seen in screenshots come from the **Privacy Witness
Kernel add-on's MQTT bridge**, not from this integration: the **Verify Now**
button (`button.pwk_verify_now`) and the daily-digest sensor
(`sensor.pwk_daily_digest`) appear only when that bridge runs in daemon mode.

## Install

**Fastest (Home Assistant OS):** one narrated, idempotent command from the
Terminal & SSH app installs and wires the whole stack — broker, Frigate, the
kernel app, this integration and its config entry, blueprints, dashboards:

```bash
curl -fsSL https://raw.githubusercontent.com/kmay89/securaCV/main/scripts/install.sh | bash
```

**By hand:**

[![Open your Home Assistant instance and add this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kmay89&repository=securacv-homeassistant&category=integration)

The badge adds this repository to HACS in one click (SecuraCV is not in the
default HACS store yet). Or manually: HACS → **⋮ → Custom repositories** → add
`https://github.com/kmay89/securacv-homeassistant` as an **Integration**.

Then install **SecuraCV** from HACS, restart Home Assistant, go to
**Settings → Devices & Services → Add Integration → SecuraCV**, and keep the
default **"Automatic — detect what's installed"** — it probes for a running
kernel and configures the right mode with nothing to type.

Requires Home Assistant 2024.4.1 or newer, with [HACS](https://hacs.xyz)
installed.

## Which setup do you need?

**Have Canary devices?** You only need an MQTT broker (the Mosquitto app
works). The **Automatic** default covers this; your Canaries auto-discover
within about 30 seconds of connecting — no kernel required. Full walkthrough:
[Home Assistant setup guide](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md).

**Witnessing cameras (Frigate or standalone)?** That's the Privacy Witness
Kernel, which runs separately. The easiest way is the Home Assistant **app**
(older Home Assistant calls these add-ons) from the main repository —
[add the app repository in one click](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkmay89%2FsecuraCV)
— or run it as a Docker container or service. See the
[one-command quick start](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#quick-start-one-command).

Running both at once is fully supported — the **Automatic** mode picks it
when a kernel answers, and the app announces itself to Home Assistant so the
integration appears as a discovered card on its own.

## Configuration

Everything is a UI config flow — no YAML required. The integration supports
MQTT (Canary devices), the kernel's Event API, or both. For the Event API,
prefer the rotating **token file** (the kernel app writes it to
`/config/api_token`); the integration re-reads it automatically when the token
rotates.

After setup, two things are worth a minute each: add the **SecuraCV Verified
Timeline** card to a dashboard (edit a dashboard → Add Card → search
"SecuraCV") for the verified-✓ event timeline, and import the
[alert blueprint](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#step-5-set-up-notifications)
for one-click phone notifications (tamper, smoke/CO heard, chain failure,
offline).

## Development

This repository is the **distribution home** for the integration. The one
distribution-only addition is `custom_components/securacv/brand/`, the icon
and logo staged for the `home-assistant/brands` submission. HACS does not read
them from here — it takes integration icons from the brands repository only —
so until that submission is merged the integration shows without an icon, and
the folder rides along into `config/custom_components/` unused. Everything else
is byte-identical to the monorepo (`.github/workflows/mirror-freshness.yml`
checks that weekly and on every PR). Development
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
