# SecuraCV Home Assistant integration

**Witnessing without watching.** SecuraCV is the verified witness log for
Frigate and Home Assistant. Frigate keeps the video; SecuraCV keeps the
proof: every person, car, dog or cat event Frigate reports is sealed into a
signed, hash-chained log as a coarse claim — which camera, which ten-minute
window, what kind of thing — and never a face, a plate, a name or a frame.
This integration brings that log into Home Assistant, checks it with Home
Assistant's own chain walk, and exports it as a signed evidence pack anyone
can verify offline. **Canary** witness devices — the project's own small
witnesses — join the same integration over MQTT, each with its own signed
chain.

## What it creates

- **One SecuraCV device per witness kernel** (the SecuraCV app on Home
  Assistant OS, or the Docker sidecar beside Frigate): **Last Event**,
  **Chain Valid**, **Chain Length**, **Daily digest**, **Online**, **Frigate
  link**, the **Kernel key fingerprint**, storage health, and two buttons,
  **Verify now** and **Export evidence**
  ([every entity](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#step-4-verify-discovery)).
- **One witness event entity per camera** (`event.securacv_front_door` for
  the Frigate camera `front_door`), created on its first sealed event and
  fired on every live one — what automations and the blueprints trigger on.
  Each event carries the camera, the ten-minute window, the event class and
  the verdict below; never a precise time, a name, a plate or a frame.
- **Sealed ✓, Verified ✓ or Failed ⚠ on every kernel event.** *Sealed*: the
  kernel signed it into its chain. *Verified*: the integration itself
  fetched the sealed log, recomputed every hash link and checked every
  Ed25519 signature against the key it pinned when you connected — the word
  is earned by Home Assistant's own check, never by the kernel's say-so.
  *Failed*: the last walk rejected the chain. A changed witness key is never
  shown as Failed; it is a Repairs issue that shows both fingerprints for
  you to compare
  ([what the badges mean](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#what-sealed--verified--and-failed--mean)).
- **A dashboard that builds itself.** **Settings → Dashboards → Add
  dashboard → SecuraCV**: chain status with **Verify now** and **Export
  evidence**, today's verified timeline, one tile per camera with an *Open
  Frigate* link, the 24-hour digest, health, and your Canaries — nothing to
  configure, no entity ids to type. Two cards for dashboards of your own,
  the **Verified Timeline** and the **Aim Camera** (a boxes-only aiming
  view for Canary Vision), load with no resource to add: edit a dashboard →
  **Add Card** → search "SecuraCV"
  ([the dashboard](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#add-the-dashboard)).
- **Two actions for the witness log.** `securacv.verify` walks the chain
  now; the **Verify now** button runs the same walk. `securacv.export_evidence`
  writes one zip under `<config>/securacv/evidence` — the kernel's signed
  bundle verbatim, the offline evidence viewer, a README for the recipient
  and the witness key — announced with a download link signed for 24 hours
  and listed under **Media → SecuraCV evidence**. Send the whole zip to
  whoever needs to check it
  ([actions](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#actions)).
- **Notifications with proof attached.** The
  [blueprints](https://github.com/kmay89/securaCV/blob/main/docs/blueprints/README.md)
  import with one click each: *Witness notification with proof* (a Frigate
  alert becomes one push once SecuraCV has sealed it, with **Open Frigate**
  and **Export evidence** actions), the *Daily digest* (it always sends, so
  a quiet night reads as a quiet night, with the chain state), *Quiet-hours
  activity & silent zone*, and the Canary alerts. The app and the
  one-command installer place them under
  `/config/blueprints/automation/securacv/` for you.
- **A device per Canary**, its entities appearing as the Canary first
  reports them: Last Event, Witness Count, Chain Length, Health, Online,
  Motion and Occupancy; Tamper, plus one sensor per tamper type; SD-card
  wear and GPS fix, which stay empty or read "no fix" on a model without
  that hardware; and, on the models that report them, radar link and mesh
  and Chirp status. **Chain Valid** per Canary is on only when the Canary
  reports its chain intact and that publish carried an Ed25519 signature
  that checked against its pinned device key — the same meaning of
  "verified", nothing looser.
- **Three actions for
  [watches](https://github.com/kmay89/securaCV/blob/main/docs/design/watches.md)**,
  bounded attention that ends by itself: `securacv.start_watch`,
  `securacv.end_watch` and `securacv.list_watches`.
- **Assist voice answers** with Home Assistant's own conversation agent: "is
  the fleet OK?", "what did I miss?", "keep an eye on the gate for two
  weeks". Voice can ask and can start a watch; no sentence arms, disarms,
  mutes or unseals anything. **One manual step:** copy
  [`voice_sentences_en.yaml`](https://github.com/kmay89/securaCV/blob/main/docs/voice_sentences_en.yaml)
  to `/config/custom_sentences/en/securacv.yaml` and restart Home Assistant.
  Until then Assist does not know the sentences
  ([voice guide](https://github.com/kmay89/securaCV/blob/main/docs/voice_control.md);
  the app's setup wizard copies the file for you).
- **Repairs issues that say what to do**: Home Assistant's MQTT integration
  not connected, no witness kernel found yet, the kernel unreachable, the
  witness key changed (with a fix flow that shows both fingerprints),
  storage replacement recommended, and a one-time table when the
  integration replaced the app's older `pwk_*` entities.

## Install with HACS

[![Open your Home Assistant instance and add this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kmay89&repository=securacv-homeassistant&category=integration)

1. Add this repository to HACS with the badge above. SecuraCV is not in the
   default HACS store yet, so by hand it is HACS → **⋮ → Custom
   repositories** → `https://github.com/kmay89/securacv-homeassistant`, type
   **Integration**.
2. Install **SecuraCV** from HACS and restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → SecuraCV**, and keep
   the default **Automatic — detect what's installed**: it looks for the
   SecuraCV app, then listens for a Docker sidecar's signed announcement on
   your broker, and sets up what it finds with nothing to type. Finding
   neither, it sets up the MQTT-only entry for Canary devices, says so, and
   connects by itself once a kernel appears.

Requires **Home Assistant 2026.5.0 or newer** and [HACS](https://hacs.xyz).
Frigate events also need an MQTT broker Home Assistant and Frigate share
(the Mosquitto app works) and **Frigate 0.14 or newer with MQTT enabled**.
The integration shows its own icon, served from its bundled `brand/`
folder; the HACS dashboard may still show the generic placeholder, since it
fetched icons from its own feed when this was written
([hacs/integration#5171](https://github.com/hacs/integration/issues/5171)).

## Then connect a witness kernel

Frigate's events are witnessed by the **Privacy Witness Kernel**, which runs
beside Frigate and announces itself to this integration. Canary devices
need only the broker: they are discovered within about 30 seconds of
connecting, no kernel needed
([Canary walkthrough](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#manual-walkthrough-canary-via-mqtt)).

| You run | Install this | What you type |
|---|---|---|
| **Home Assistant OS** | the **SecuraCV** app from the App Store ([add the app repository](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkmay89%2FsecuraCV)); its wizard reads Frigate's cameras from Frigate's own config, and its done screen can install this integration for you if HACS has not | nothing |
| **Home Assistant Container** beside a Docker Frigate | the [Docker sidecar](https://github.com/kmay89/securaCV/blob/main/docs/frigate_integration.md#quick-start-docker-no-home-assistant) next to Frigate (one compose file, two lines to edit) | one 6-digit code |

**The app.** Once it runs, **Settings → Devices & Services** shows a
*SecuraCV app* discovered card. Press **Configure**; the form has no fields.
Frigate events appear as sealed witness events within a minute of the next
detection
([Path 1](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#path-1-home-assistant-os--the-securacv-app)).

**The sidecar.** It announces itself on the broker with a signed message;
the discovered *SecuraCV sidecar* card shows the kernel's key fingerprint,
and `docker exec securacv pair` on the Docker host prints a 6-digit code
beside the same fingerprint. Compare the two, enter the code, done: Home
Assistant exchanges it for a long-lived paired token (revocable with
`docker exec securacv unpair`, or by removing the integration entry) and
pins the kernel's key from that authenticated answer, never from the
broadcast
([Path 3](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md#path-3-home-assistant-container-and-the-docker-sidecar)).

**The whole stack in one command (Home Assistant OS).** From the Terminal &
SSH app, this narrated, idempotent script installs the broker, Frigate, the
SecuraCV app, this integration and its config entry, the blueprints and the
dashboard:

```bash
curl -fsSL https://raw.githubusercontent.com/kmay89/securaCV/main/scripts/install.sh | bash
```

Then **Settings → Dashboards → Add dashboard → SecuraCV**, and walk past a
camera: the first event reads **Sealed ✓** within a minute, **Verified ✓**
once the integration has walked the chain. The full walkthrough with the
exact screens, every entity and troubleshooting is the
[setup guide](https://github.com/kmay89/securaCV/blob/main/docs/homeassistant_setup.md).

## Configuration

Setup is a UI config flow, with no YAML to write. **Automatic** is right for
almost everyone; the manual modes are there for a kernel that announces
nothing. For the app, the kernel's API is reached through the rotating
**token file** the app writes to `/config/api_token`, which the integration
re-reads when the token rotates. For the sidecar, the pairing code above
replaces the token. **Reconfigure** on the entry changes the address, the
credential or the MQTT prefix without losing the kernel's pin; a kernel
that starts rejecting the credential asks to re-authenticate with a fresh
code.

**Witness keys.** The kernel's verifying key is pinned when you connect,
and every chain walk checks against that pin. A different key later — a
restore to new hardware, a reinstalled app or sidecar, or something else
answering at that address — raises **The witness kernel's key changed** in
Settings → Repairs with the pinned and the received fingerprints; the fix
flow asks you to confirm the new one against what the kernel itself prints
before it rotates the pin, and the events stay Sealed ✓ (never Failed)
meanwhile.

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

## What crosses your network

The record is **tamper-evident**: it makes interference visible, never
impossible, and "verified" here always means an Ed25519 signature checked
against a pinned key.

**The sidecar's API is plain HTTP for now.** The paired token Home Assistant
holds crosses your LAN in the clear on port 8799 until TLS with a pinned
fingerprint lands for the sidecar, so keep that port on your own network
and never forward it from the internet
([what the published port opens](https://github.com/kmay89/securaCV/blob/main/docs/security/SECURITY_MODEL.md#home-assistant-pairing-and-what-crosses-your-network)).
The app on Home Assistant OS has no such port: Home Assistant reaches it
inside the Supervisor network.

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
