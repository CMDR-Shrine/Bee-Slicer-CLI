#!/usr/bin/env python3
"""Inspect BEE G-code offline. Uses only the Python 3 standard library."""
import argparse
import json
import math
from pathlib import Path
import re

COMMAND = re.compile(r"^(?:N\d+\s*)?([GMT])(\d+)(?=[\sA-Za-z*]|$)", re.I)
PARAMETER = re.compile(r"([A-Z])\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))", re.I)
EFFECTS = {
    "M24": "No M24 dispatch in inspected BEE firmware; autonomous SD start uses M33.",
    "M130": "Sets heater PID coefficients and writes persistent configuration when T/U/V are supplied.",
    "M206": "Sets acceleration using X; this is not a Marlin home-offset command.",
    "M642": "Sets firmware extrusion coefficient using W; can compound slicer flow adjustment.",
    "M31": "Sets estimated minutes (A) and command count (L); copied job metadata becomes stale.",
    "M703": "Heating workflow also homes/moves the printer; it is not a plain temperature wait.",
    "M112": "This firmware's stop handler also homes the printer; do not assume a motion-free stop.",
    "M609": "Requests a restart into bootloader mode.",
}


def inspect(path, manifest=None):
    counts, first_lines, temperatures, findings = {}, {}, [], []
    bed_targets, executable_lines = [], 0
    with open(path, "r", encoding="utf-8", errors="replace") as stream:
        for number, raw in enumerate(stream, 1):
            line = raw.split(";", 1)[0].strip()
            if not line:
                continue
            executable_lines += 1
            match = COMMAND.match(line)
            if not match:
                continue
            command = match[1].upper() + str(int(match[2]))
            counts[command] = counts.get(command, 0) + 1
            first_lines.setdefault(command, number)
            parameters = {k.upper(): float(v) for k, v in PARAMETER.findall(line[match.end():])}
            if command in ("M104", "M109"):
                for parameter in ("S", "R"):
                    target = parameters.get(parameter)
                    if target is not None and target > 0 and math.isfinite(target):
                        temperatures.append({"line": number, "command": command, "target_c": target})
                        break
            if command in ("M140", "M190") and max(parameters.get("S", 0), parameters.get("R", 0)) > 0:
                bed_targets.append(number)
            if command in EFFECTS and counts[command] == 1:
                findings.append({"line": number, "command": command, "note": EFFECTS[command]})
    unknown = []
    if manifest:
        supported = manifest["firmware_dispatch_commands"]
        unknown = sorted(c for c in counts if c[0] in supported and int(c[1:]) not in supported[c[0]])
    return {
        "file": str(Path(path).resolve()),
        "executable_lines": executable_lines,
        "commands": dict(sorted(counts.items())),
        "first_positive_nozzle_target_c": temperatures[0]["target_c"] if temperatures else None,
        "nozzle_temperature_commands": temperatures,
        "heated_bed_command_lines": bed_targets,
        "bee_command_notes": findings,
        "not_in_inspected_firmware_dispatch": unknown,
        "scope": "Offline source comparison, not a guarantee of compatibility with the installed firmware. No USB access or commands sent.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    manifest_path = Path(__file__).resolve().parent.parent / "docs/upstream/manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
        result = inspect(args.file, manifest)
    except (OSError, ValueError) as exc:
        parser.exit(2, "Inspection failed: %s\n" % exc)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
