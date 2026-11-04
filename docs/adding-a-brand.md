# Adding a brand

Every Intesis INMBS single-unit gateway (`INMBSxxx001R000`) shares one register
map. What differs per AC brand is data: the mode, fan speed and vane code maps,
the error table, and the device id reported in register 49. The multi-unit
gateways (`INMBSxxxXXXO000`) work the same way with their own code maps.

To add a brand:

1. Get the brand's single-unit manual from HMS. The URL follows the pattern
   `https://www.hms-networks.com/docs/default-source/products/intesis/manuals-and-guides---manuals/user-manual-inmbs<brand>001r000.pdf`
   (`dai`, `pan`, `tos`, `lge`, `hit`, `sam`, ...). `pdftotext -layout` extracts it.
2. Copy `intesis_gw_modbus/brands/mhi.py` to `intesis_gw_modbus/brands/<key>.py`.
   Fill in `key`, `name`, `device_id` (register 49, "Device ID" in the manual's
   register table), the three single-unit code maps (registers 1, 2 and 3), the
   three multi-unit code maps if the brand has a multi-unit gateway (block
   offsets 2, 4 and 6; leave the MHI values if the manual matches), and the
   error table from the manual's "Error Codes" section, transcribed verbatim.
3. Register the table in `BRANDS` (`intesis_gw_modbus/brands/__init__.py`) and
   add the brand's part numbers to `MODELS` (`intesis_gw_modbus/models.py`).
   Remove the device id from `KNOWN_DEVICE_IDS` if it was listed there.
4. Run `pytest`. The round-trip test over `BRANDS` picks the new table up on its
   own; add a test for the error table's size and a couple of rows, like
   `test_mhi_error_table`.
5. Mention the gateway in the README's supported devices table.

Nothing in the device classes or the Home Assistant integration needs to change.
