# ActivityWatch for Home Assistant

Home Assistant integration for [ActivityWatch](https://activitywatch.net), the open-source, privacy-first automated time tracker.

Surfaces device activity from an [aw-server](https://docs.activitywatch.net/) instance as Home Assistant entities, enabling automations like:

- **"At desk" presence detection** — trigger scenes when you start/stop using a computer
- **Focus-mode lights** — react to which app is in the foreground
- **Screen-time awareness** — dashboards and notifications based on daily usage

## Entities

One device is created per tracked host, each with:

| Entity | Type | Description |
|---|---|---|
| Active | `binary_sensor` (occupancy) | Whether the host is in active use (not AFK) |
| Screen time today | `sensor` (duration) | Total active time since local midnight |
| Current app | `sensor` | Foreground application (cleared when not active) |
| Current window title | `sensor` | Foreground window title — **disabled by default**, see below |
| Last seen | `sensor` (timestamp) | End of the last activity event |

## Privacy design

ActivityWatch data is intimate; this integration is deliberately **not** full access:

- It only reads AFK status, the latest window event, and a daily screen-time aggregate. It never touches browser history, editor activity, or input buckets, and it never writes anything.
- The **window title sensor is disabled by default** — titles can contain message contents, document names, and URLs. Enable it per-host only if you want it, and note that anything in Home Assistant's state machine lands in its recorder database and is visible to all HA users and integrations.
- Diagnostics dumps redact window titles.
- You choose exactly which hosts to expose during setup; stale/synced buckets on the server are not exposed unless selected.

### A note on network exposure

`aw-server` has **no authentication** and binds to `127.0.0.1` by default. For Home Assistant to reach it you must expose it on a network interface (`aw-server --host 0.0.0.0`, a reverse proxy, or an SSH/VPN tunnel). Anyone who can reach that port can read *all* your ActivityWatch data — only do this on a trusted network, ideally scoped with firewall rules to just your Home Assistant host.

## Installation

### HACS (custom repository)

1. HACS → three-dot menu → *Custom repositories* → add this repo as type *Integration*
2. Install **ActivityWatch**, restart Home Assistant
3. Settings → Devices & services → *Add integration* → ActivityWatch
4. Enter the aw-server host/port, then pick which hosts to track

### Manual

Copy `custom_components/activitywatch/` into your Home Assistant `config/custom_components/` directory and restart.

## Development

```sh
uv venv --python 3.13
uv pip install pytest-homeassistant-custom-component ruff
.venv/bin/pytest
```

## Roadmap to Home Assistant core

This integration is built with core submission in mind (config flow, `DataUpdateCoordinator`, entity translations, diagnostics, tests). Remaining before a core PR:

- [ ] Extract the API client into a published async library (async support in [aw-client](https://github.com/ActivityWatch/aw-client))
- [ ] Add to [home-assistant/brands](https://github.com/home-assistant/brands)
- [ ] Bake in HACS default repository inclusion, gather usage feedback
- [ ] Quality-scale checklist (reconfigure flow, repair issues, more tests)

## License

MIT. Core ActivityWatch is MPL-2.0, but this integration is deliberately permissive: Home Assistant core contributions are relicensed Apache-2.0 under the HA CLA, and an MIT history means external contributions to this repo can be upstreamed into core without relicensing friction.
