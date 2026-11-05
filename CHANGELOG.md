# Changelog

## 0.1.0 (2026-11-05)

- Single-unit gateways (`INMBSxxx001R000`): full register map, typed device,
  three temperature formats, brand auto-detection by device id.
- Multi-unit gateways (`INMBSxxx048O000`, `INMBSxxx128O000`): per-indoor-unit
  views and all-units commands, modelled from the manual (untested on hardware);
  units that come online later are discovered by re-probing empty blocks.
- Mitsubishi Heavy Industries brand table.
