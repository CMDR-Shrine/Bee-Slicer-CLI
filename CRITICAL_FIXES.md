# Workflow fixes (2026-10-01)

The current runtime is Python 3, with a native BEE protocol implementation based on the inspected manufacturer sources. See [README](README.md) for commands and validation limits, and [upstream research](docs/UPSTREAM_RESEARCH.md) for evidence.

Changes:

- Calibration uses `G131 Z...`, absolute Z jogs, three `G132` advances, and final `G28` cleanup. First-point advance saves height; cancellation before it does not. Commands are acknowledged and movement waits are bounded.
- Transfer uses 32 KiB ranges and 512-byte messages with explicit acknowledgements; failures never proceed to heating/start.
- Heating timeouts prevent print/filament actions and attempt heater shutdown before a print start request.
- Preheat chooses the nozzle setting before initial extrusion; later layer temperatures remain in the prepared job unless explicitly overridden.
- Status handling normalizes case and requires the actual printing state, not merely `M32` progress fields.
- Monitoring attaches without USB reset, mode changes or reconfiguration; local locking avoids simultaneous CLI clients.
- Load/unload use material temperatures, wait for firmware operations to finish, and cool afterward.
- Prepared copies remove stale metadata and copied `M130` persistent heater PID writes, while retaining source files.
- Correct command meanings: `M206 X` is acceleration; `M130` writes PID; `M642 W` is firmware extrusion flow; `M33` accepts an optional filename.
- `M32 C/D` can be bytes when command metadata is absent; monitoring labels them as counters.
- Bootloader transitions are permitted for explicit actions, not passive monitoring. No firmware flashing is performed.

The previous scripts and edits are archived under `backups/`. The previous document's `cardreader.cpp` lowercase explanation was not supported by the inspected stock firmware. Lowercase selection is retained as a historical working convention, not attributed to that file.

All verification performed so far is offline/simulated. Hardware timing, USB protocol behavior and physical calibration must be checked on the printer before treating them as verified.
