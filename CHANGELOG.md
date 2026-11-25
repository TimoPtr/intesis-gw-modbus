# Changelog

## 0.3.1 (2026-11-25)

Both fixes follow from reading an INMBSMHI001R000 while it initialises.

- `operation_hours` of a single-unit gateway no longer reads as `None` at
  exactly 32768 hours. The counter covers the whole register and keeps its
  value while the gateway initialises.
- While a single-unit gateway initialises, `power`, `mode`, `fan_speed`,
  `alarm` and `control_lock` are `None`. The gateway reads placeholders for
  them during those two minutes (off, auto, an alarm) that are not the state
  of the unit.

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
