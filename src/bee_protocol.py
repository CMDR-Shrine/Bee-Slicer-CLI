"""Bounded Python 3 BEE protocol, based on BEECom and stock firmware sources."""
import math
import re
import time

ACK = r"\bok\s+q:\s*\d+(?:\s|$)"


class PrinterError(RuntimeError):
    pass


def parse_status(response):
    match = re.search(r"\bS:\s*(\d+)\b", response, re.I)
    if not match:
        raise PrinterError("No printer status in response: " + repr(response))
    code = int(match[1])
    name = {0: "Error", 3: "Ready", 4: "Moving", 5: "Printing", 6: "Transferring", 7: "Paused", 9: "Shutdown"}.get(code, "Unknown")
    if "shutdown" in response.lower():
        name = "Shutdown"
    elif "pause" in response.lower():
        name = "Paused"
    return code, name


def parse_progress(response):
    values = dict((key.upper(), int(value)) for key, value in re.findall(r"\b([ABCD])(\d+)\b", response, re.I))
    if set(values) != set("ABCD"):
        raise PrinterError("Incomplete print progress: " + repr(response))
    return {"estimated_seconds": values["A"] * 60, "elapsed_seconds": values["B"] / 1000,
            "total": values["C"], "current": values["D"],
            "percent": min(100, values["D"] * 100 / values["C"]) if values["C"] else None}


class UsbTransport:
    """Attach to active USB configuration without reset or reconfiguration."""
    def __init__(self, serial=None):
        import usb.core
        import usb.util
        self.core, self.util = usb.core, usb.util
        self.device = None
        candidates = list(usb.core.find(idVendor=0x29C9, find_all=True))
        candidates += list(usb.core.find(idVendor=0xFFFF, idProduct=0x014E, find_all=True))
        if serial:
            candidates = [d for d in candidates if self._serial(d) == serial]
        if not candidates:
            raise PrinterError("No BEE printer found. Check USB power, cable and permissions.")
        if len(candidates) != 1:
            raise PrinterError("Multiple BEE printers found; select one with --serial.")
        self.device = candidates[0]
        try:
            config = self.device.get_active_configuration()
            interface = config[(0, 0)]
            self.output = usb.util.find_descriptor(interface, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
            self.input = usb.util.find_descriptor(interface, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
            if self.output is None or self.input is None:
                raise PrinterError("BEE USB endpoints are missing.")
        except Exception as exc:
            self.close()
            raise PrinterError("Cannot attach to BEE USB interface: %s" % exc) from exc

    @staticmethod
    def _serial(device):
        try:
            return device.serial_number
        except Exception:
            return None

    def write(self, data, timeout=2000):
        if isinstance(data, str):
            data = data.encode("ascii")
        try:
            written = self.output.write(data, timeout=timeout)
        except self.core.USBError as exc:
            raise PrinterError("USB write failed: %s" % exc) from exc
        if written != len(data):
            raise PrinterError("Incomplete USB write (%s/%s bytes)." % (written, len(data)))
        return written

    def read(self, timeout=500):
        # Match BEECom Conn.read(): an empty OUT packet precedes every IN read.
        # This is a USB packet, not a G-code command or a payload retry.
        self.write(b"", timeout=timeout)
        try:
            return bytes(self.input.read(512, timeout=timeout)).decode("ascii", errors="replace")
        except self.core.USBTimeoutError:
            return ""
        except self.core.USBError as exc:
            raise PrinterError("USB read failed: %s" % exc) from exc

    def close(self):
        if self.device is not None:
            self.util.dispose_resources(self.device)
            self.device = None


class Protocol:
    def __init__(self, transport, clock=time.monotonic, sleep=time.sleep):
        self.transport, self.clock, self.sleep = transport, clock, sleep

    def receive(self, pattern=ACK, timeout=10, allow_error=False):
        deadline, response = self.clock() + timeout, ""
        while self.clock() < deadline:
            response += self.transport.read(timeout=max(1, min(500, int((deadline - self.clock()) * 1000))))
            if not allow_error and re.search(r"error|bad [gm]-code|position not ok|can't", response, re.I):
                raise PrinterError("Printer rejected operation: " + response.strip())
            if re.search(pattern, response, re.I):
                return response
            if len(response) > 32768:
                raise PrinterError("Unexpectedly large printer response.")
        if re.search(r"\btog\b", response, re.I):
            raise PrinterError("Received file-transfer acknowledgement instead of a command reply; the printer may still be in an interrupted binary upload. If no print is running, fully power-cycle the printer before retrying (USB reconnect alone may not clear it). Response: " + repr(response[-300:]))
        raise PrinterError("Printer response timed out: " + repr(response[-300:]))

    def command(self, command, pattern=ACK, timeout=10, allow_error=False):
        self.transport.write(command.rstrip() + "\n")
        return self.receive(pattern, timeout, allow_error)

    def status(self):
        return parse_status(self.command("M625", r"(?s)\bS:\s*\d+\b.*"+ACK))

    def require_idle(self):
        code, name = self.status()
        if code != 3 or name != "Ready":
            raise PrinterError("Printer must be Ready; current state is %s (%s)." % (name, code))

    def wait_state(self, expected, timeout=60):
        deadline=self.clock()+timeout
        while self.clock()<deadline:
            code,state=self.status()
            if state in expected:
                return
            if code==0:
                raise PrinterError("Printer entered Error state.")
            self.sleep(.25)
        raise PrinterError("Printer did not reach %s within %s seconds." % (expected,timeout))

    def wait_ready(self, timeout=60):
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            response = self.command("M625", r"(?s)\bS:\s*\d+\b.*"+ACK, timeout=min(10, max(.1, deadline-self.clock())))
            code, name = parse_status(response)
            if code == 0:
                raise PrinterError("Printer entered Error state.")
            queue = re.search(r"\bQ:\s*(\d+)\b", response, re.I)
            if code == 3 and name == "Ready" and (queue is None or int(queue[1]) == 0):
                return
            self.sleep(.25)
        raise PrinterError("Movement/operation did not finish within %s seconds." % timeout)

    def temperature(self, during_print=False):
        pattern = r"\bT:\s*[-+]?\d+(?:\.\d+)?(?:\s|$)"
        if not during_print:
            pattern = "(?s)" + pattern + r".*"+ACK
        response = self.command("M105", pattern)
        value = float(re.search(r"\bT:\s*([-+]?\d+(?:\.\d+)?)", response, re.I)[1])
        if not math.isfinite(value):
            raise PrinterError("Invalid nozzle temperature.")
        return value

    def heat(self, target, timeout=300, progress=None):
        if not math.isfinite(target) or not 150 <= target <= 250:
            raise PrinterError("Choose a finite temperature between 150 and 250 C.")
        self.command("M104 S%g" % target)
        started = self.clock()
        deadline, next_report, current = started + timeout, started, None
        while self.clock() < deadline:
            current = self.temperature()
            ready = abs(current - target) <= 2
            now = self.clock()
            if progress and (now >= next_report or ready):
                progress(current, target, now-started)
                next_report = now + 5
            if ready:
                return
            self.sleep(1)
        raise PrinterError("Heating timed out after %g seconds (last nozzle %s C, target %g C); print/filament operation was not started." % (timeout, "%g" % current if current is not None else "unknown", target))

    def transfer(self, data, name="ABCDE", timeout=300, progress=None):
        if not data:
            raise PrinterError("Cannot transfer an empty G-code file.")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,7}", name):
            raise PrinterError("SD filename must start with a letter and contain 1–8 letters/digits.")
        deadline = self.clock() + timeout
        def remaining(limit=10):
            value = deadline-self.clock()
            if value <= 0:
                raise PrinterError("File transfer timed out; print was not started.")
            return min(limit, value)
        self.command("M21", timeout=remaining())
        self.command("M30 " + name, r"file created[^\r\n]*\s*"+ACK, timeout=remaining())
        # SDK protocol: 32 KiB ranges divided into 512-byte messages, each acknowledged by 'tog'.
        for start in range(0, len(data), 512 * 64):
            block = data[start:start+512*64]
            end = start + len(block) - 1
            try:
                self.command("M28 D%d A%d" % (end, start), r"ok\s+q:\s*0\b", timeout=remaining())
            except PrinterError as exc:
                raise PrinterError("Transfer could not open byte range %d–%d: %s; print was not started." % (start, end, exc)) from exc
            for offset in range(0, len(block), 512):
                frame = block[offset:offset+512]
                try:
                    self.transport.write(frame)
                    # BEECom sendBlockMsg deliberately yields before reading.
                    self.sleep(.001)
                    # BEECom permits ten reads of up to two seconds per frame.
                    self.receive(r"tog", timeout=remaining(20))
                except PrinterError as exc:
                    raise PrinterError("Transfer failed awaiting acknowledgement for bytes %d–%d (of %d): %s; no payload retry, heating or print start was sent." % (start+offset, start+offset+len(frame)-1, len(data), exc)) from exc
            if progress:
                progress(start + len(block), len(data))

    def start_print(self, name="ABCDE", timeout=30):
        self.command("M21")
        self.command("M23 " + name.lower())
        self.command("M33", timeout=timeout)
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            code, state = self.status()
            if code == 5 and state == "Printing":
                return
            if code == 0 or state == "Shutdown":
                raise PrinterError("Printer failed to start: " + state)
            self.sleep(.25)
        raise PrinterError("Print start was not confirmed; check the printer before retrying.")


class Calibration:
    def __init__(self, protocol):
        self.protocol, self.active, self.point, self.z = protocol, False, 0, 2.0

    def start(self, start_z=2):
        if not math.isfinite(start_z) or not .5 <= start_z <= 5:
            raise PrinterError("Calibration starting gap must be 0.5–5 mm.")
        self.protocol.require_idle()
        self.protocol.command("G90")
        self.active = True  # Include cleanup if G131 times out after beginning motion.
        self.protocol.command("G131 Z%g" % start_z, timeout=60)
        self.protocol.wait_ready()
        self.z, self.point = start_z, 1

    def jog(self, delta):
        if self.point != 1 or not math.isfinite(delta) or abs(delta) > .5:
            raise PrinterError("Only jog Z in increments up to 0.5 mm at the first point.")
        target = round(self.z + delta, 3)
        if not -1 <= target <= 5:
            raise PrinterError("Requested Z is outside the calibration adjustment range (-1 to 5 mm).")
        # Absolute Z removes the old leak of G91 into firmware-managed point changes.
        self.protocol.command("G90")
        self.protocol.command("G1 Z%g F120" % target)
        self.protocol.wait_ready()
        self.z = target

    def next(self):
        if self.point not in (1, 2, 3):
            raise PrinterError("Calibration is not at an active point.")
        self.protocol.command("G90")
        self.protocol.command("G132", timeout=60)
        self.protocol.wait_ready()
        self.point += 1
        if self.point == 4:
            # G132 ends with home(), but G28 also explicitly clears is_calibrating.
            self.protocol.command("G28", timeout=60)
            self.protocol.wait_ready()
            self.active = False

    def cancel(self):
        if self.active:
            self.protocol.command("G90")
            self.protocol.command("G28", timeout=60)
            self.protocol.wait_ready()
            self.active = False
