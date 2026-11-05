# intesis-gw-modbus Agent Guide

You are helping develop `intesis-gw-modbus`, a typed Python model of the
Intesis INMBS Modbus gateways that put air-conditioner indoor units on a
Modbus RTU or TCP bus. It is built on
[modbus-connection](https://pypi.org/project/modbus-connection/): the library
declares registers as `Component` classes and takes a `ModbusUnit`; it never
opens a link. Its main consumer is the Home Assistant core integration
`intesis_modbus`, which must keep working whenever the public API changes.

The project is independent of HMS Networks and Intesis; keep the README's
disclaimer and never present the library as official.

## Essential commands

```bash
pip install -e ".[dev]"
pytest                                   # whole suite; 100 % coverage is enforced
pytest tests/test_single_unit_device.py --no-cov  # one file; the gate fails any partial run
mypy intesis_gw_modbus tests/            # strict
ruff check . && ruff format --check .    # select = ["ALL"], run before committing
yamllint .                               # workflows and renovate config
```

Everything runs against the `modbus-connection` mock backend (`mock_modbus_unit`
fixture, seeders in `tests/conftest.py`). Nothing talks to hardware, and the
owner's gateways are not available for testing: do not add tests or scripts
that need a real unit.

## Layout

- `intesis_gw_modbus/enums.py`: `Mode`, `FanSpeed`, `VanePosition`,
  `TemperatureFormat`, `ErrorState`, `GatewayFamily`. Values are stable
  strings; Home Assistant translates them.
- `temperature.py`: the three DIP-switch formats and `INIT_VALUE` (0x8000).
  Every temperature the library returns or accepts is in degrees Celsius.
- `errors.py`: exceptions and `decode_error`. `ac.py`: the `AirConditioner`
  protocol both gateway families satisfy.
- `brands/`: one data table per AC brand (`base.py` defines `BrandTable`,
  `mhi.py` is the reference). Brand data is data, never code; see
  `docs/adding-a-brand.md`.
- `models.py`: part numbers in `MODELS`, device ids of brands without a table
  in `KNOWN_DEVICE_IDS`, `model_for_device_id`.
- `single_unit/`: `INMBSxxx001R000` (`components.py` registers, `device.py`
  `IntesisSingleUnitGateway`). `multi_unit/`: `INMBSxxx048O000` / `128O000`
  (`IndoorUnitView` per unit, `IntesisMultiUnitGateway`).

## Development standards

- Every source and test file starts with `# Copyright (c) 2026 Timothy (TimoPtr)`.
- Python 3.12 is the floor (`requires-python`, ruff `target-version`, mypy
  `python_version`); use 3.12 syntax such as PEP 695 generics freely.
- Test-driven: write the failing test first, watch it fail, then write the
  minimal code. No production change without a test that failed before it.
- Keep the 100 % coverage gate honest: a test must fail if the behaviour it
  names is removed. Do not corrupt unrelated registers to force an assertion.
- Module constants are `Final`; a bare `Final` with a literal is fine, write
  `Final[float]` only when the literal would infer the wrong type.
- Docstrings are imperative one-liners (ruff D401); comments explain why, never
  what.
- Register facts come from the Intesis manuals and are transcribed verbatim
  (addresses, code maps, error tables, English descriptions). Cite the manual
  revision and section in the docstring or comment. Do not commit the PDFs;
  they are copyrighted. The MHI manuals are r6.4 (single-unit) and r1.0
  (multi-unit).
- Hardware behaviour the manual does not state is unknown, not assumed. Say so
  in a comment and keep a test that pins the chosen behaviour. Hardware facts
  in the README go under the gateway family they were read from.

## Modbus rules the gateways impose

- A block read must not touch an undefined address: read the documented
  ranges only, one request each (`register_ranges`). Writes are single
  registers; function 16 is limited to one register on the single-unit gateway
  and absent on the multi-unit one.
- Data registers hold `INIT_VALUE` (0x8000) while the gateway initialises;
  declare `nan=INIT_VALUE` on every field that can show it so readings become
  `None` instead of garbage.
- Timing defaults (`_REQUIRED_TIMEOUT`, `_MESSAGE_SPACING`) are conservative
  guesses derived from the bus parameters, not measurements.

## Behaviour the integration relies on

- Readings are `None` when unknown; setters raise `UnsupportedValueError` for
  values the unit cannot take and let `ModbusError` propagate.
- Single-unit: `detected_temperature_format` reflects the DIP switches each
  poll; `available_fan_speeds` follows register 21 through
  `BrandTable.fan_speeds_for`; `async_set_external_temperature(None)` writes
  `INIT_VALUE` to hand regulation back to the unit's own sensor.
- Multi-unit: setup probes every block once and raises `NoIndoorUnitsError`
  when none answers (the caller retries). Each poll reads every known unit's
  block on its own: a failed block marks that unit not `present` while the
  others refresh, and `units` fails only when every block failed. Each update
  re-probes `REDISCOVERY_BATCH` empty or refused blocks round-robin, so late
  units join `indoor_units`; a unit that drops out stays listed with `present`
  false and every reading `None`.
- Non-finite temperatures (NaN, infinity) are rejected with
  `UnsupportedValueError` before any register is touched; setpoint limits are
  checked in register units so a rounded Celsius bound never rejects a value
  that encodes to the limit itself.
- A `WrongGatewayError` means the device id does not belong to the model and
  the caller must stop, not retry.

## Changelog, releases and CI

- Add user-visible behaviour changes to `CHANGELOG.md` under the unreleased
  version.
- Releases are GitHub releases tagged `vX.Y.Z`; `publish.yml` builds from the
  tag (version from `setuptools-scm`) and publishes through trusted publishing.
- Workflows pin actions by SHA, declare the least permissions, and document
  every permission with a comment; `zizmor` must stay clean. Renovate keeps
  dependencies and actions current (`renovate.json5`).

## Pull requests

Keep pull requests small and focused, with the tests that prove them. A human
reviews, understands and can explain every change before it is submitted: do
not open issues or pull requests, and do not post review replies, without the
maintainer's go-ahead.
