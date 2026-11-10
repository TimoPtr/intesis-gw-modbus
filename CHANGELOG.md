# Changelog

## Unreleased

- `async_probe_gateway(unit)` identifies a gateway before a device is built
  for it: the model its device id belongs to, the brand of a documented
  gateway without a table, the temperature format and whether a vane position
  was reported. A register the gateway does not have reads as absent; a busy
  or silent gateway raises so the caller can retry.

## 0.1.0 (2026-11-05)

- Single-unit gateways (`INMBSxxx001R000`): full register map, typed device,
  three temperature formats, brand auto-detection by device id.
- Multi-unit gateways (`INMBSxxx048O000`, `INMBSxxx128O000`): per-indoor-unit
  views and all-units commands, modelled from the manual (untested on hardware);
  units that come online later are discovered by re-probing empty blocks.
- Mitsubishi Heavy Industries brand table.
