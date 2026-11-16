# Changelog

## 0.3.0 (2026-11-16)

- A single-unit gateway now follows the temperature format its DIP switches
  select: after each poll of the readings, `temperature_format` is set to the
  format detected from the setpoint register. The format passed to the
  constructor only serves until the gateway reports a setpoint, so a caller no
  longer has to compare `detected_temperature_format` itself.

## 0.2.0 (2026-11-10)

- `async_probe_gateway(unit)` identifies a gateway before a device is built
  for it: the model its device id belongs to, the brand of a documented
  gateway without a table, the temperature format and whether a vane position
  was reported. Only single-unit gateways are identified; a multi-unit
  gateway comes back with no model. A register the gateway does not have
  reads as absent; a busy or silent gateway raises so the caller can retry.

## 0.1.0 (2026-11-05)

- Single-unit gateways (`INMBSxxx001R000`): full register map, typed device,
  three temperature formats, brand auto-detection by device id.
- Multi-unit gateways (`INMBSxxx048O000`, `INMBSxxx128O000`): per-indoor-unit
  views and all-units commands, modelled from the manual (untested on hardware);
  units that come online later are discovered by re-probing empty blocks.
- Mitsubishi Heavy Industries brand table.
