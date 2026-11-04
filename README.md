# intesis-gw-modbus

Python library for [Intesis](https://www.intesis.com) INMBS Modbus gateways, the
boxes that put an air conditioner's indoor unit on a Modbus RTU or TCP bus.
Built on [modbus-connection](https://pypi.org/project/modbus-connection/): the
library models the registers and takes a `ModbusUnit`; it never opens a link.

This library was built with the help of [Claude](https://claude.ai) (Anthropic).

## Supported gateways

| Gateway | Family | Status |
|---|---|---|
| INMBSMHI001R000 (Mitsubishi Heavy Industries, RTU) | single-unit | modelled from the manual (r6.4), verified against the mock backend |
| INMBSMHI048O000 / INMBSMHI128O000 (MHI, RTU or TCP) | multi-unit | modelled from the manual (r1.0), verified against the mock backend only |

The single-unit register map is shared by the other brands' `INMBSxxx001R000`
gateways. Their device ids are known (Daikin `0x0801`, Panasonic `0x1500`,
Toshiba `0x1F00`, LG `0x1000`, Hitachi `0x1400`, Samsung `0x1200`) but their
code and error tables are not written yet: see
[docs/adding-a-brand.md](docs/adding-a-brand.md).

## Home Assistant

A core Home Assistant integration (`intesis_modbus`) built on this library is
in progress.

## Installation

```bash
pip install intesis-gw-modbus
```

Requires Python 3.12+ and `modbus-connection`.

## Usage

```python
import asyncio

from modbus_connection import ModbusSerialParams
from modbus_connection.tmodbus import ModbusConnection

from intesis_gw_modbus import (
    MODELS,
    FanSpeed,
    IntesisSingleUnitGateway,
    TemperatureFormat,
)


async def main() -> None:
    connection = ModbusConnection(
        ModbusSerialParams(device="/dev/ttyUSB0", baudrate=9600, stopbits=2)
    )
    try:
        unit = connection.for_unit(1)
        gateway = IntesisSingleUnitGateway(
            unit,
            brand=MODELS["INMBSMHI001R000"].brand,
            temperature_format=TemperatureFormat.DECICELSIUS,
        )
        report = await gateway.async_update()
        print(
            report.updated, gateway.mode, gateway.setpoint, gateway.current_temperature
        )
        await gateway.async_set_fan_speed(FanSpeed.HIGH)
        await gateway.async_set_setpoint(22.5)
    finally:
        await connection.close()


asyncio.run(main())
```

Every temperature the library returns or accepts is in degrees Celsius,
whatever the gateway's DIP-switch format. `detect_temperature_format(raw)`
infers the format from a raw setpoint register when it is not known.

A multi-unit gateway is `IntesisMultiUnitGateway(unit, brand=..., unit_count=48)`;
after the first `async_update()` its `indoor_units` dict holds one
`IndoorUnitView` per unit the gateway talks to.

## Hardware notes

The single-unit gateway speaks Modbus RTU at 9600 baud, 8N2, address 1 by
default. Its DIP switches set the address (SW3), the baud rate (SW3/SW4), the
temperature format (SW4: x1 °C, x10 °C or °F) and the 120 Ω termination (SW4);
every change needs a power cycle.

Only function codes 3, 4, 6 and 16 are implemented, and a block read must not
touch an undefined address. The library therefore reads the documented blocks
only, one request each. Timing defaults (`require_timeout(3.0)`,
`set_message_spacing(0.02)`) are conservative values derived from the bus
parameters, not measured; both live in the device classes.

## Development

```bash
pip install -e ".[dev]"
pytest            # 100 % coverage is enforced
mypy intesis_gw_modbus tests/
ruff check . && ruff format --check .
```

Everything runs against the `modbus-connection` mock backend; no hardware is
needed.

## Releasing

Publishing a GitHub release tagged `vX.Y.Z` builds the package from that tag
(the version comes from `setuptools-scm`) and publishes it to PyPI through
trusted publishing.

## License

Apache-2.0.
