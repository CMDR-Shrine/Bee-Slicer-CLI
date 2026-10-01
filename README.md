# BEETHEFIRST / BEETHEFIRST+ CLI

Python 3 tools for slicing with PrusaSlicer, transferring G-code through BEE USB, printing, material handling, monitoring and firmware-guided bed calibration.

The current implementation uses the BEE protocol documented by the manufacturer's SDK and firmware. The old Python 2 SDK and its API documentation are archived in `backups/legacy-python2-20261001.tar.gz`. No Miniconda, Python 2, Docker or pyserial is needed.

## Setup

```bash
cd /home/zac/Documents/Projects/VIBE/VIBE-Bee-Slicer-CLI
uv sync
./print.sh --help
```

The project environment needs only PyUSB (installed by `uv sync`) and the system libusb library. Python 3.10 or later is required. The environment has been installed on this machine. Offline inspection, slicing and dry runs never open USB.

USB access still needs the existing udev/group permissions. On Arch, use the `uucp` group rather than Ubuntu's `dialout`. Check the existing `config/99-beeverycreative.rules` before installing rules for your distribution. Permission errors are reported; the CLI does not use sudo, kill other processes, reset USB, or stop Docker automatically. Close BEEsoft/BEEweb while using these tools. A local lock prevents simultaneous hardware operations from this CLI; it cannot coordinate with unrelated applications.

On this Arch machine, install the rule and enable access with:

```bash
sudo usermod -aG uucp zac
sudo install -m 644 config/99-beeverycreative.rules /etc/udev/rules.d/99-beeverycreative.rules
sudo udevadm control --reload-rules
```

Reconnect USB and log out/in, or run `newgrp uucp` to activate membership in a new shell. Run the CLI as your regular user.

## Commands

Run `./print.sh` for a menu or use these commands directly:

| Command | Purpose |
| --- | --- |
| `./print.sh inspect part.gcode` | Offline command and temperature report |
| `./print.sh print part.gcode --dry-run` | Validate and report the prepared job without USB |
| `./print.sh slice part.stl --material polylite-pla --quality -o part.gcode` | Slice with the installed BEE PrusaSlicer profiles |
| `./print.sh print part.gcode` | Transfer, heat, start autonomous SD printing and confirm its state |
| `./print.sh part.gcode` | Compatibility shorthand for print |
| `./print.sh calibrate` | Interactive firmware-guided bed leveling |
| `./print.sh load --material petg` | Material-aware load; cool after completion |
| `./print.sh unload --material polylite-pla` | Material-aware unload; cool after completion |
| `./print.sh status` | One status/temperature/progress snapshot |
| `./print.sh monitor` | Poll every five seconds; Ctrl+C closes monitoring |
| `./print.sh monitor --once` | Single monitor snapshot |
| `./print.sh pause` / `resume` / `cancel` | Explicit print controls with state checks |
| `./print.sh firmware` | Start the already installed firmware if in bootloader; does not flash |

Hardware commands accept `--serial SERIAL` when multiple printers are attached. `monitor` supports `--interval SECONDS`. Print supports `--transfer-timeout` and `--heat-timeout`, both defaulting to 300 seconds.

Materials are `pla`, `polylite-pla` and `petg`. Load/unload defaults to PolyLite PLA at 215 C; generic PLA starts at 210 C and Polymaker PETG at 240 C. You can specify `--temperature 240` explicitly. PETG slicing selects the experimental unheated-bed preset. The print command normally preserves the temperatures in the sliced file; `--temperature` deliberately replaces every positive nozzle target in the prepared copy. CLI temperatures are limited to 150–250 C. Check the actual hotend and material before using PETG; firmware software limits are not hardware ratings.

## Calibration

Use a clean nozzle below 50 C and the usual paper gauge. The new wizard uses line input followed by ENTER, so it works over SSH and ordinary terminals.

```bash
./print.sh calibrate
```

1. Firmware `G131 Z2` homes and moves to point A with a 2 mm initial gap. `--start-z` accepts 0.5–5 mm.
2. Enter `u` to move the bed closer by 0.05 mm, or `d` to move it away by 0.05 mm. Uppercase `U/D` uses 0.5 mm steps. Every move uses absolute positioning at a controlled speed and waits for completion. The software adjustment range is -1 to 5 mm; watch the paper/nozzle while adjusting.
3. Enter `n` when the gauge feels correct. The first `G132` **saves the height to printer configuration** and moves to point B. Adjust the left screw and press ENTER.
4. Firmware advances to point C. Adjust the right screw and press ENTER to finish and home. Final `G28` explicitly clears calibration mode.
5. Enter `q` or Ctrl+C to exit calibration and home. If you already advanced from point A, its saved height remains; cancellation does not undo a hardware setting already saved.

The old blind writes and leaking relative mode were removed. Both normal and canceled sequences clean up the connection. You can check your existing first-layer pattern afterward:

```bash
./print.sh gcode/calibration.gcode --temperature 215 --dry-run
./print.sh gcode/calibration.gcode --temperature 215
```

The existing test pattern and your old calibration changes were preserved in the rollback archive. The CLI does not automatically print a calibration pattern after leveling.

## Printing and monitoring behavior

Jobs are fully validated before SD is touched. File transfer is synchronous: firmware acknowledges each byte range and 512-byte message. Missing acknowledgements, creation errors, partial USB writes and timeouts stop the workflow before print start. No failed block is blindly replayed.

USB reads send BEECom's empty OUT packet before reading IN. Transfer frames retain BEECom's 1 ms pause and permit up to 20 seconds for acknowledgement, within the overall transfer deadline. Transfer errors identify the byte range that failed; these compatibility changes still need hardware verification. After a stalled transfer, the firmware may remain in binary receive mode. If the failed attempt stopped before heating or printing and the printer is idle, power-cycle it before retrying.

The prepared copy uses plain ASCII G-code, fresh `M31` time/command metadata, absolute positioning, a nozzle wait and homing. Input files are never edited. Redundant unsupported `G21/M82`, old `M31/M1033`, heater-off bed commands, and copied persistent PID writes (`M130`) are removed and reported. Active bed heating, relative extrusion, inch mode, binary G-code and commands missing from the inspected firmware dispatcher are rejected. Firmware `M642` extrusion coefficients and other supported file settings are retained; tune slicer flow with those in mind.

The preheat target is the last positive nozzle setting before the first positive extrusion move, rather than the last temperature anywhere in the job. This handles ordinary staged startup and different later-layer temperatures. Files without a suitable target require an explicit temperature. This is a static interpretation, not a full G-code simulation.

The internal SD destination remains `ABCDE`, preserving the working convention. Selection uses lowercase `abcde`; autonomous printing uses `M33`. A confirmed printing state is required before reporting success. Print returns once start is confirmed; the printer then runs autonomously. Closing a monitor does not cancel a print. If a start request was sent but confirmation fails, the CLI reports uncertainty and does not retry automatically.

Monitor/status attach to the active USB configuration without device reset, reconfiguration, mode switching, homing or heating. They do send read queries. Firmware state matching is case-insensitive. Progress counters may represent commands or bytes for jobs started by other hosts, so they are labeled as counters. Bootloader printers must enter firmware before monitoring; mutating actions can start the installed firmware and reconnect explicitly.

Pause/resume wait for confirmed states. **Cancel calls BEE's `M112`, whose handler also homes the printer.** It is a print-cancel action, not a guaranteed motion-free emergency stop.

## Implementation and validation

- `src/bee_protocol.py`: USB attach, bounded responses, block transfer, temperatures, status and calibration controller.
- `src/bee_cli.py`: argument validation, prepared jobs and workflows.
- `src/print.py`, `calibrate.py`, `load.py`, `unload.py`, `monitor.py`: compatibility entrypoints for Python 3.
- [Source investigation](docs/UPSTREAM_RESEARCH.md): protocol evidence and historical issues.
- `docs/upstream/`: selected manufacturer reference files and snapshot manifest. The manifest supplies the firmware command list used by inspection and print validation.

```bash
uv run --no-sync python -m unittest discover -s tests -v
```

Tests simulate protocol responses, multi-block transfers, startup failures, heater timeouts, calibration save/cancel, USB attachment and material handling. Offline slicing and dry runs passed. **Physical USB operation and calibration still need verification on the actual printer.** No live printer commands were issued during implementation.

Rollback archive: `backups/before-workflow-fixes-20261001.tar.gz`. It contains the previous shell entrypoint, all five workflow scripts (including your uncommitted calibration edits), and bundled SDK. Do not extract it over current files unless deliberately rolling back.
