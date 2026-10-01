#!/usr/bin/env python3
"""BEE printer CLI. Hardware actions occur only inside main(), after argument validation."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from bee_protocol import ACK, Calibration, PrinterError, Protocol, UsbTransport, parse_progress, parse_status
from inspect_gcode import inspect

ROOT = Path(__file__).resolve().parent.parent
MATERIALS = {
    "pla": (210, "Generic PLA @ BEETHEFIRST+"),
    "polylite-pla": (215, "Polymaker PolyLite PLA @ BEETHEFIRST+"),
    "petg": (240, "Polymaker PETG @ BEETHEFIRST+ Experimental"),
}
NUMBER = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))"
LINE = re.compile(r"^(?:N\d+\s*)?([GMT])(\d+)(?=[\sA-Za-z*]|$)", re.I)


def valid_temperature(value):
    value = float(value)
    if not math.isfinite(value) or not 150 <= value <= 250:
        raise argparse.ArgumentTypeError("Temperature must be between 150 and 250 C.")
    return value


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("Value must be positive and finite.")
    return value


def prepare_job(path, temperature=None):
    """Prepare a copy; never edit input. Keep motion/extrusion settings from the file."""
    path = Path(path)
    if path.suffix.lower() != ".gcode":
        raise PrinterError("Print requires a plain .gcode file; use slice for a model.")
    if path.read_bytes()[:4] == b"GCDE":
        raise PrinterError("Binary G-code is not supported by BEE firmware.")
    manifest = json.loads((ROOT / "docs/upstream/manifest.json").read_text())
    supported = manifest["firmware_dispatch_commands"]
    lines, removed, targets, selected, extruded = [], {}, [], None, False
    estimate = 0
    for raw in path.read_text(encoding="utf-8", errors="strict").splitlines():
        duration = re.search(r"estimated printing time \(normal mode\)\s*=\s*(.*)", raw)
        if duration:
            estimate = sum(int(n)*{"d":86400,"h":3600,"m":60,"s":1}[unit] for n,unit in re.findall(r"(\d+)\s*([dhms])",duration[1]))
        code = raw.split(";", 1)[0].strip()
        if not code:
            continue
        match = LINE.match(code)
        if not match:
            raise PrinterError("Unsupported G-code syntax: " + code[:100])
        command = match[1].upper() + str(int(match[2]))
        # SD copies do not need serial line numbers/checksums; normalize numeric fields for BEE's parser.
        code = code[match.start(1):].split("*", 1)[0].strip()
        code = re.sub(r"([a-z])(?=\s*[-+.\d])",lambda field:field[1].upper(),code)
        match = LINE.match(code)
        params = {k.upper():float(v) for k,v in re.findall(r"([A-Z])\s*"+NUMBER,code[match.end():],re.I)}
        if command in ("G21", "M82", "M31", "M1033", "M130"):
            removed[command] = removed.get(command, 0) + 1
            continue
        if command in ("M140", "M190"):
            if max(params.get("S", 0), params.get("R", 0)) > 0:
                raise PrinterError("This stock BEE profile has no heated bed; file requests bed heating.")
            removed[command] = removed.get(command, 0) + 1
            continue
        if command == "G20" or command == "M83":
            raise PrinterError("BEE jobs must use millimetres and absolute extrusion.")
        if command[0] not in supported or int(command[1:]) not in supported[command[0]]:
            raise PrinterError("Command absent from inspected BEE firmware: " + command)
        if command in ("M104", "M109"):
            # BEE M109 uses S, not Marlin's R parameter.
            if "R" in params or "S" not in params:
                raise PrinterError("BEE temperature commands require an S parameter.")
            target = params["S"]
            if target > 250 or target < 0:
                raise PrinterError("Nozzle target outside supported CLI range (0–250 C).")
            if target > 0:
                targets.append(target)
                if not extruded:
                    selected = target
        if command in ("G0", "G1") and params.get("E", 0) > 0:
            extruded = True
        lines.append(code)
    if not lines or not extruded:
        raise PrinterError("File contains no extrusion moves to print.")
    target = temperature if temperature is not None else selected
    if target is None:
        raise PrinterError("No nozzle target before extrusion; specify --temperature or re-slice.")
    if not math.isfinite(target) or not 150 <= target <= 250:
        raise PrinterError("Preheat target must be 150–250 C.")
    # Explicit override replaces active temperature commands as well as preheat.
    if temperature is not None:
        lines = [re.sub(r"(?i)S\s*"+NUMBER, "S%g" % target, line)
                 if re.match(r"M(?:104|109)(?=[\sS])",line,re.I) and float(re.search(r"S\s*"+NUMBER,line,re.I)[1]) > 0 else line for line in lines]
    body = ["G90", "M109 S%g" % target, "G28"] + lines
    # M31 counts include both its own command and the inserted header commands.
    body.insert(0, "M31 A%d L%d" % (estimate//60, len(body)+1))
    return ("\n".join(body)+"\n").encode("ascii"), {"target_c": target, "removed_commands": removed, "estimated_seconds": estimate, "commands": len(body)}


def print_job(protocol, path, temperature=None, transfer_timeout=300, heat_timeout=300):
    data, report = prepare_job(path, temperature)
    protocol.require_idle()
    print("Prepared %s commands; preheat %g C." % (report["commands"],report["target_c"]))
    if report["removed_commands"]:
        print("Prepared copy removed redundant/stale setup commands: " + str(report["removed_commands"]))
    heated, start_requested = False, False
    try:
        protocol.transfer(data, timeout=transfer_timeout, progress=lambda done,total: print("Transfer %.1f%%" % (100*done/total)))
        print("Transfer complete. Heating nozzle to %g C (timeout %g seconds)..." % (report["target_c"], heat_timeout), flush=True)
        heated = True
        protocol.heat(report["target_c"], timeout=heat_timeout,
                      progress=lambda current,target,elapsed: print("Heating: %.1f / %g C (%.0f seconds)" % (current,target,elapsed),flush=True))
        print("Nozzle ready. Starting SD print and waiting for confirmation...",flush=True)
        start_requested = True
        protocol.start_print()
        print("Print start confirmed. Use monitor to watch progress.")
    except BaseException:
        if heated and not start_requested:
            try:
                protocol.command("M104 S0")
            except Exception:
                print("Could not confirm heater shutdown; check the printer.", file=sys.stderr)
        if start_requested:
            print("Start was requested. Check printer state before retrying; no automatic restart was sent.",file=sys.stderr)
        raise


def monitor(protocol, once=False, interval=5):
    while True:
        code,state = protocol.status()
        temp = protocol.temperature(during_print=code==5)
        parts = [state, "Nozzle %.1f C" % temp]
        if state in ("Printing", "Paused", "Shutdown"):
            progress = parse_progress(protocol.command("M32",r"(?s)\bA\d+\s+B\d+\s+C\d+\s+D\d+.*"+ACK))
            # Firmware C/D can be commands or bytes; do not pretend to know which for other hosts' jobs.
            parts += ["Progress %s" % ("%.1f%%" % progress["percent"] if progress["percent"] is not None else "unknown"),
                      "Counters %s/%s" % (progress["current"],progress["total"]),
                      "Elapsed %.0f s" % progress["elapsed_seconds"]]
            if progress["estimated_seconds"]:
                parts.append("Remaining ~%.0f s" % max(0,progress["estimated_seconds"]-progress["elapsed_seconds"]))
        print(" | ".join(parts),flush=True)
        if once:
            return
        time.sleep(interval)


def filament(protocol, operation, temperature):
    protocol.require_idle()
    try:
        protocol.heat(temperature)
        # Firmware M703 intentionally homes and moves into the load/unload position.
        protocol.command("M703 S%g" % temperature,timeout=90)
        protocol.wait_ready(timeout=90)
        protocol.command("M701" if operation=="load" else "M702",timeout=120)
        protocol.wait_ready(timeout=120)
        print("Filament %s finished." % operation)
    finally:
        protocol.command("M104 S0")


def calibration(protocol, start_z=2, ask=input):
    controller = Calibration(protocol)
    try:
        print("Use a clean, cool nozzle and your usual paper gauge. G132 saves the first-point height.")
        protocol.require_idle()
        if protocol.temperature()>50:
            raise PrinterError("Cool the nozzle below 50 C before paper calibration.")
        controller.start(start_z)
        print("Point A: bed-height adjustment. closer=Z-0.05, away=Z+0.05; uppercase=0.5 mm.")
        while controller.point == 1:
            key = ask("[u/U closer, d/D away, n save and advance, q cancel]: ").strip()
            if key in ("u","U","d","D"):
                controller.jog({"u":-.05,"U":-.5,"d":.05,"D":.5}[key])
                print("Z %.2f mm" % controller.z)
            elif key=="n":
                controller.next()
            elif key=="q":
                return
        for description in ("Point B: adjust the left screw using your paper gauge.","Point C: adjust the right screw using your paper gauge."):
            print(description)
            key=ask("ENTER to advance, q to cancel: ").strip().lower()
            if key=="q":
                return
            if key:
                raise PrinterError("Unexpected calibration input; canceled.")
            controller.next()
        print("Calibration sequence completed. Check a small first-layer print next.")
    finally:
        if controller.active:
            print("Ending calibration and homing. Saved first-point height, if already advanced, is retained.")
            controller.cancel()


def slice_model(args):
    binary=shutil.which("prusa-slicer")
    if not binary:
        raise PrinterError("PrusaSlicer executable not found.")
    preset = "BEETHEFIRST+ 0.20 mm PETG Experimental" if args.material=="petg" else "BEETHEFIRST+ 0.15 mm Quality" if args.quality else "BEETHEFIRST+ 0.20 mm Balanced"
    command=[binary,"--printer-profile","BEETHEFIRST+ 0.4 mm","--print-profile",preset,
             "--material-profile",MATERIALS[args.material][1],"--export-gcode","--output",str(args.output),str(args.model)]
    subprocess.run(command,check=True)


def parser():
    p=argparse.ArgumentParser(description="BEE printer tools (Python 3). Monitor/status attach without USB reset.")
    sub=p.add_subparsers(dest="action",required=True)
    for name in ("print","calibrate","load","unload","monitor","status","pause","resume","cancel","firmware"):
        q=sub.add_parser(name)
        q.add_argument("--serial",help="USB serial number when multiple BEE printers are connected")
        if name=="print":
            q.add_argument("file",type=Path)
            q.add_argument("--temperature",type=valid_temperature)
            q.add_argument("--transfer-timeout",type=positive,default=300)
            q.add_argument("--heat-timeout",type=positive,default=300)
            q.add_argument("--dry-run",action="store_true",help="prepare/report only, without USB")
        if name in ("load","unload"):
            q.add_argument("--material",choices=MATERIALS,default="polylite-pla")
            q.add_argument("--temperature",type=valid_temperature)
        if name=="calibrate":
            q.add_argument("--start-z",type=positive,default=2)
        if name=="monitor":
            q.add_argument("--once",action="store_true")
            q.add_argument("--interval",type=positive,default=5)
    q=sub.add_parser("inspect");q.add_argument("file",type=Path)
    q=sub.add_parser("slice");q.add_argument("model",type=Path);q.add_argument("--output","-o",type=Path,required=True)
    q.add_argument("--material",choices=MATERIALS,default="polylite-pla");q.add_argument("--quality",action="store_true")
    return p


def connect_printer(serial=None, allow_firmware_switch=False, factory=UsbTransport, sleep=time.sleep, clock=time.monotonic):
    transport=factory(serial)
    try:
        protocol=Protocol(transport)
        response=protocol.command("M625",pattern=r"bad m-code 625|"+ACK,allow_error=True)
        if "bad m-code 625" not in response.lower():
            protocol.status()  # Validate a fresh, complete response rather than treating any 'ok' as firmware.
            return transport,protocol
        if not allow_firmware_switch:
            raise PrinterError("Printer is in bootloader mode. Run './print.sh firmware' before monitoring.")
        print("Starting installed firmware (no flashing)...")
        transport.write("M630\n")
        transport.close()
        deadline=clock()+30
        last_error=None
        while clock()<deadline:
            sleep(.5)
            candidate=None
            try:
                candidate=factory(serial)
                protocol=Protocol(candidate)
                response=protocol.command("M625",timeout=min(5,max(.1,deadline-clock())))
                parse_status(response)
                return candidate,protocol
            except (PrinterError,OSError) as exc:
                last_error=exc
                if candidate is not None:
                    candidate.close()
        raise PrinterError("Installed firmware did not reconnect: %s" % last_error)
    except BaseException:
        transport.close()
        raise


def menu():
    actions={"1":"print","2":"load","3":"unload","4":"monitor","5":"calibrate","6":"status"}
    print("1 Print | 2 Load | 3 Unload | 4 Monitor | 5 Calibrate | 6 Status | q Exit")
    choice=input("Choice: ").strip()
    if choice=="q":
        return None
    if choice not in actions:
        raise PrinterError("Unknown menu choice.")
    action=actions[choice]
    if action=="print":
        return [action,input("G-code path: ").strip()]
    if action in ("load","unload"):
        material=input("Material [pla/polylite-pla/petg; default polylite-pla]: ").strip() or "polylite-pla"
        return [action,"--material",material]
    return [action]


def main(argv=None):
    args_list=list(sys.argv[1:] if argv is None else argv)
    transport=None
    try:
        if not args_list:
            args_list=menu()
            if args_list is None:
                return 0
        if args_list[0].lower().endswith(".gcode"):
            args_list.insert(0,"print")
        args=parser().parse_args(args_list)
        if args.action=="inspect":
            print(json.dumps(inspect(args.file,json.loads((ROOT/"docs/upstream/manifest.json").read_text())),indent=2));return 0
        if args.action=="slice":
            slice_model(args);return 0
        if args.action=="print":
            _,report=prepare_job(args.file,args.temperature)  # Validate before claiming USB or truncating SD.
            if args.dry_run:
                print(json.dumps(report,indent=2));return 0
        # Lock all our hardware commands. No automatic process kills or container stops.
        lock_dir=Path(os.environ.get("XDG_RUNTIME_DIR",tempfile.gettempdir()))
        with (lock_dir/("bee-slicer-%d.lock" % os.getuid())).open("a") as lock:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                raise PrinterError("Another BEE CLI command is using the printer; close its monitor first.")
            transport,protocol=connect_printer(args.serial,args.action in ("print","calibrate","load","unload","firmware"),factory=UsbTransport)
            if args.action=="print":print_job(protocol,args.file,args.temperature,args.transfer_timeout,args.heat_timeout)
            elif args.action=="calibrate":calibration(protocol,args.start_z)
            elif args.action in ("load","unload"):filament(protocol,args.action,args.temperature or MATERIALS[args.material][0])
            elif args.action in ("monitor","status"):monitor(protocol,args.action=="status" or args.once,args.interval if args.action=="monitor" else 5)
            elif args.action=="pause":
                if protocol.status()[1]!="Printing":raise PrinterError("Pause requires an active print.")
                protocol.command("M640",timeout=60)
                protocol.wait_state({"Paused"})
                print("Pause confirmed.")
            elif args.action=="resume":
                if protocol.status()[1] not in ("Paused","Shutdown"):raise PrinterError("Resume requires Paused or Shutdown state.")
                protocol.command("M643",timeout=60)
                protocol.wait_state({"Printing"},timeout=300)
                print("Resume confirmed.")
            elif args.action=="cancel":
                if protocol.status()[1] not in ("Printing","Paused","Shutdown"):raise PrinterError("There is no active print to cancel.")
                print("Canceling print; BEE firmware also homes the printer.")
                protocol.command("M112",timeout=60);protocol.wait_ready();print("Print canceled.")
            elif args.action=="firmware":print("Installed firmware is ready.")
        return 0
    except KeyboardInterrupt:
        print("Stopped. A running autonomous print is not canceled by closing this client.",file=sys.stderr);return 130
    except EOFError:
        print("Input closed; interactive operation ended.",file=sys.stderr);return 1
    except (PrinterError,OSError,ValueError,ImportError,subprocess.CalledProcessError) as exc:
        print("ERROR: %s" % exc,file=sys.stderr);return 1
    finally:
        if transport is not None:
            transport.close()


if __name__=="__main__":
    sys.exit(main())
