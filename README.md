# SecuraCV Home Assistant integration

**Witnessing without watching.** The Home Assistant integration for
[SecuraCV](https://github.com/kmay89/securaCV), a local-first witness layer
that records **what happened** as signed events, never footage and never
identity. It connects Home Assistant to **Canary** witness devices (over
MQTT) and to the **Privacy Witness Kernel** (the signed, hash-chained event
log).

## What it creates

- **A device per Canary**, its entities appearing as the Canary first
  reports them: Last Event (a semantic event such as "large object crossed
  boundary"), Witness Count, Chain Length, Health, Online, Motion and
  Occupancy; Tamper, plus one sensor per tamper type; SD-card wear and GPS
  fix, which stay empty or read "no fix" on a model without that hardware;
  and, on the models that report them, radar link and mesh and Chirp status
  ([full list](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#step-4-verify-discovery)).
- **Chain Valid** per Canary: on only when the Canary reports its chain
  intact and that publish carried an Ed25519 signature that checked against
  its pinned device key. That is what "verified" means here, nothing looser;
  re-verifying a whole log is the kernel app's job.
- **A kernel device**, when a kernel is configured: its last event, Online,
  and storage health, wear, free space and write rate, and SoC temperature.
- **Two Lovelace cards**, the Verified Timeline and the Aim Camera (a
  boxes-only aiming view for Canary Vision), loaded automatically, with no
  dashboard resource to add: edit a dashboard → **Add Card** → search
  "SecuraCV".
- **Three actions for
  [watches](https://github.com/kmay89/securaCV/blob/main/docs/design/watches.md)**,
  bounded attention that ends by itself: `securacv.start_watch`,
  `securacv.end_watch` and `securacv.list_watches`
  ([how to call them](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#actions)).
- **Assist voice answers** with Home Assistant's own conversation agent: "is
  the fleet OK?", "what did I miss?", "keep an eye on the gate for two
  weeks". Voice can ask and can start a watch; no sentence arms, disarms,
  mutes or unseals anything.
  **One manual step:** copy
  [`voice_sentences_en.yaml`](https://github.com/kmay89/securaCV/blob/main/docs/voice_sentences_en.yaml)
  to `/config/custom_sentences/en/securacv.yaml` and restart Home Assistant.
  Until then Assist does not know the sentences
  ([voice guide](https://github.com/kmay89/securaCV/blob/main/docs/voice_control.md);
  its setup wizard copies the file for you).
- **A Repairs issue** if Home Assistant's MQTT integration is not connected,
  saying how to fix it.

The **Verify Now** button (`button.pwk_verify_now`) and the daily-digest
sensor (`sensor.pwk_daily_digest`) come from the Privacy Witness Kernel
app's MQTT bridge in daemon mode, not from this integration.

## Install with HACS

[![Open your Home Assistant instance and add this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kmay89&repository=securacv-homeassistant&category=integration)

1. Add this repository to HACS with the badge above. SecuraCV is not in the
   default HACS store yet, so by hand it is HACS → **⋮ → Custom
   repositories** → `https://github.com/kmay89/securacv-homeassistant`, type
   **Integration**.
2. Install **SecuraCV** from HACS and restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → SecuraCV**, and keep
   the default **"Automatic — detect what's installed"**: it looks for a
   running kernel and sets up the right mode with nothing to type.

Requires Home Assistant 2024.4.1 or newer and [HACS](https://hacs.xyz). On
Home Assistant 2026.3 or newer the integration shows its own icon, served
from its bundled `brand/` folder. Older versions show the generic
placeholder (the [brands](https://github.com/home-assistant/brands) CDN has
no SecuraCV entry), and so may the HACS dashboard, which fetched icons from
its own feed when this was written
([hacs/integration#5171](https://github.com/hacs/integration/issues/5171)).

**The whole stack in one command (Home Assistant OS).** From the Terminal &
SSH app, this narrated, idempotent script installs the broker, Frigate, the
kernel app, this integration and its config entry, blueprints and
dashboards:

```bash
curl -fsSL https://raw.githubusercontent.com/kmay89/securaCV/main/scripts/install.sh | bash
```

## Which setup do you need?

**Canary devices** need only an MQTT broker (the Mosquitto app works); no
kernel. They are discovered within about 30 seconds of connecting
([setup guide](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md)).

**Cameras (Frigate or standalone)** are witnessed by the Privacy Witness
Kernel, which runs separately: as a Home Assistant app
([add the app repository](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkmay89%2FsecuraCV)),
a Docker container or a service
([quick start](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#quick-start-one-command)).
Running both at once is supported; the app announces itself, so the
integration shows up as discovered.

**Canary to broker is plain by default.** Canaries speak plain MQTT on port
`1883`, so the broker login crosses your LAN in the clear. Every
MQTT-speaking Canary except the nightstand-c6 display can be provisioned
for TLS on `8883` from either flasher or its own setup page, checked against
a CA certificate you supply or, on most models, pinned to the broker
certificate's SHA-256 fingerprint. A half-finished TLS setup refuses to
connect rather than falling back to plain. On the broker side, the hub
plan's opt-in `sh provision.sh --with broker_tls` points the Mosquitto app
at a certificate and key you place in Home Assistant's `ssl` folder; it
mints no certificate and does not check that the listener came up, and Home
Assistant's own MQTT connection stays on the internal `1883`. Honest status:
compile-tested by CI and host-tested, not yet run against a TLS broker on
hardware
([Step 3](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#step-3-configure-the-canary-device)).

## Configuration

Setup is a UI config flow, with no YAML to write. For the kernel's Event
API, use the rotating **token file** the kernel app writes to
`/config/api_token`; the integration re-reads it when the token rotates.
Import the
[alert blueprint](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#step-5-set-up-notifications)
for phone notifications on tamper, smoke or CO heard, chain failure and
offline.

**Device keys.** Each Canary's signing key is pinned the first time its
health publish carries one (trust on first use). A publish signed by a
different key later raises a notification, and that Canary's entities keep
updating, marked unverified. If your threat model includes the broker or
another client on it, pin each key by hand (**Settings → Devices &
Services → SecuraCV → Configure → Pin a device pubkey (manual)**) and
restrict publishing with broker ACLs
([Step 6](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#step-6-verify-per-device-pki-optional-but-recommended);
[where each product shows its key](https://github.com/kmay89/securaCV/blob/main/docs/device_trust.md#where-each-product-shows-its-key)).

**Apple Home.** The **Motion** and **Occupancy** sensors carry standard
device classes, so Home Assistant's HomeKit Bridge can show them in the Home
app: present-tense state only, never video, never identity, with no
signature checked on that hop, and changes reach Apple's side as your events
happen. Match them with `binary_sensor.securacv_canary_*_motion` under
`include_entity_globs`; Home Assistant refuses a `*` under
`include_entities`
([recipe](https://github.com/kmay89/securaCV/blob/main/docs/integrations/apple-home-homekit-bridge.md)).

## Development

This repository distributes the integration. Everything under
`custom_components/securacv/` (the `brand/` icon included) and the root
`conftest.py` are byte-identical copies from
[`kmay89/securaCV`](https://github.com/kmay89/securaCV), where development
happens. Please file issues and PRs there.

The monorepo's
[`homeassistant-mirror.yml`](https://github.com/kmay89/securaCV/blob/main/.github/workflows/homeassistant-mirror.yml)
copies that set here on every `main` commit that touches it, proves the copy
exact with [`check_mirror_sync.py`](.github/scripts/check_mirror_sync.py),
and opens one pull request on `bot/mirror-sync`. It needs a `MIRROR_PAT`
secret in the monorepo; without one it stays green and raises an issue
there. [`mirror-freshness.yml`](.github/workflows/mirror-freshness.yml) is
the backstop: it diffs this tree against the monorepo weekly and on every
change to the carried set, and fails on drift with the exact resync
commands. Its weekly run raises one drift issue, and the first passing run
on `main` closes it. `README.md`, `hacs.json`, `requirements_test.txt` and
the agent briefs ([`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md)) are
owned here.

Run the tests standalone:

```sh
pip install -r requirements_test.txt
pytest custom_components/securacv/tests -q \
  --deselect custom_components/securacv/tests/test_homekit_projection.py::test_mirror_matches_the_dictionary \
  --deselect custom_components/securacv/tests/test_homekit_projection.py::test_hold_window_is_sane \
  --deselect custom_components/securacv/tests/test_voice.py::test_sentences_yaml_matches_registered_intents
```

The three deselected tests read monorepo files
(`spec/witness_dictionary.json`, `docs/voice_sentences_en.yaml`) and run in
the monorepo's CI; a few more skip themselves here, each saying why.
[`tests.yml`](.github/workflows/tests.yml) also runs the pinned ruff and
mypy with the monorepo's lint config.

## License

[Apache-2.0](LICENSE), same as the main repository.
