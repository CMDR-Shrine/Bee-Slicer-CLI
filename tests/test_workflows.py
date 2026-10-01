import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from bee_protocol import Calibration, PrinterError, Protocol, UsbTransport, parse_progress, parse_status
from bee_cli import calibration, connect_printer, filament, main, prepare_job, print_job


class FakeTransport:
    """Protocol-level simulator; responses are released only after a write."""
    def __init__(self, overrides=None):
        self.now=0
        self.writes=[]
        self.replies=[]
        self.overrides=overrides or {}
        self.raw_left=0
        self.target=20
        self.printing=False
        self.closed=False

    def write(self,data,timeout=2000):
        self.writes.append(data)
        if self.raw_left:
            self.raw_left-=len(data)
            self.replies.append("tog")
            return len(data)
        command=data.decode("ascii") if isinstance(data,bytes) else data
        command=command.strip()
        if command in self.overrides:
            reply=self.overrides[command]
            self.replies.extend(reply if isinstance(reply,list) else [reply])
        elif command=="M625":self.replies.append("S:%s ok Q:0\r\n" % (5 if self.printing else 3))
        elif command=="M105":self.replies.append("T:%g %s" % (self.target,"" if self.printing else "ok Q:0\r\n"))
        elif command=="M32":self.replies.append("A10 B12000 C100 D20 ok Q:0\r\n")
        elif command.startswith("M104 S"):
            self.target=float(command.split("S")[1]);self.replies.append("ok Q:0\r\n")
        elif command.startswith("M30 "):self.replies.append("File created: ABCDE\n"+"ok Q:0\r\n")
        elif command.startswith("M28 "):
            import re
            end=int(re.search(r"D(\d+)",command)[1]);start=int(re.search(r"A(\d+)",command)[1])
            self.raw_left=end-start+1;self.replies.append("will write bytes ok Q:0\r\n")
        elif command=="M33":self.printing=True;self.replies.append("ok Q:0\r\n")
        else:self.replies.append("ok Q:0\r\n")
        return len(data)

    def read(self,timeout=500):
        self.now+=timeout/1000 if not self.replies else .001
        return self.replies.pop(0) if self.replies else ""

    def close(self):self.closed=True
    def protocol(self):return Protocol(self,lambda:self.now,self.sleep)
    def sleep(self,seconds):self.now+=seconds
    def commands(self):return [x.strip() for x in self.writes if isinstance(x,str)]


class ProtocolTests(unittest.TestCase):
    def test_status_case_and_pause_shutdown(self):
        self.assertEqual(parse_status("S:5 ok Q:0"),(5,"Printing"))
        self.assertEqual(parse_status("s:3 Pause ok"),(3,"Paused"))
        self.assertEqual(parse_status("S:3 Shutdown ok"),(3,"Shutdown"))

    def test_progress_is_not_truncated_to_minutes(self):
        result=parse_progress("A10 B1234 C0 D0 ok Q:0")
        self.assertEqual(result["elapsed_seconds"],1.234)
        self.assertIsNone(result["percent"])

    def test_split_status_consumes_ack(self):
        t=FakeTransport({"M625":["S:3 ","ok Q:0\r\n"]})
        self.assertEqual(t.protocol().status(),(3,"Ready"))
        self.assertEqual(t.replies,[])

    def test_timeout_never_blindly_continues(self):
        t=FakeTransport({"G131 Z2":""})
        with self.assertRaises(PrinterError):t.protocol().command("G131 Z2",timeout=1)
        self.assertLess(t.now,2)

    def test_interrupted_upload_at_attach_requires_power_cycle(self):
        t=FakeTransport({"M625":"tog\n"})
        with patch("bee_cli.Protocol",side_effect=lambda transport:transport.protocol()),self.assertRaisesRegex(PrinterError,"interrupted binary upload.*power-cycle"):
            connect_printer(None,True,factory=lambda _:t)
        self.assertEqual(t.commands(),["M625"])
        self.assertTrue(t.closed)

    def test_stale_transfer_ack_does_not_hide_valid_status(self):
        t=FakeTransport({"M625":["tog\n","S:3 ok Q:0\r\n"]})
        self.assertEqual(t.protocol().status(),(3,"Ready"))

    def test_error_in_ok_response_is_rejected(self):
        t=FakeTransport({"M23 abcde":"error opening file ok Q:0"})
        with self.assertRaises(PrinterError):t.protocol().start_print()
        self.assertNotIn("M33",t.commands())

    def test_fragmented_error_is_not_mistaken_for_ack(self):
        t=FakeTransport({"G131 Z2":["ok - ","Error: Bad G-code 131\n"]})
        with self.assertRaises(PrinterError):t.protocol().command("G131 Z2")

    def test_waits_for_idle_queue_after_movement(self):
        t=FakeTransport()
        statuses=iter(["S:3 ok Q:1\n","S:3 ok Q:0\n"])
        original=t.write
        def write(data,timeout=2000):
            if data=="M625\n":
                t.overrides["M625"]=next(statuses)
            return original(data,timeout)
        t.write=write
        t.protocol().wait_ready()
        self.assertEqual(t.commands(),["M625","M625"])

    def test_transfer_byte_ranges_and_binary_frames(self):
        t=FakeTransport(); data=b"G1 X1\n"*6000
        t.protocol().transfer(data)
        binary=[x for x in t.writes if isinstance(x,bytes)]
        self.assertEqual(b"".join(binary),data)
        self.assertTrue(all(len(frame)<=512 for frame in binary))
        self.assertIn("M28 D32767 A0",t.commands())
        self.assertIn("M28 D35999 A32768",t.commands())

    def test_failed_file_creation_never_sends_payload(self):
        t=FakeTransport({"M30 ABCDE":"error creating file ok Q:0"})
        with self.assertRaises(PrinterError):t.protocol().transfer(b"G28\n")
        self.assertFalse(any(isinstance(x,bytes) for x in t.writes))

    def test_transfer_yields_after_frames_before_reading(self):
        t=FakeTransport()
        events=[]
        original_write, original_read=t.write,t.read
        def write(data,timeout=2000):
            if isinstance(data,bytes):events.append("payload")
            return original_write(data,timeout)
        def sleep(seconds):
            events.append(("sleep",seconds));t.sleep(seconds)
        def read(timeout=500):
            if events and events[-1]==("sleep",.001):events.append("read")
            return original_read(timeout)
        t.write,t.read=write,read
        Protocol(t,lambda:t.now,sleep).transfer(b"G1 X1\n"*100)
        self.assertEqual(events,["payload",("sleep",.001),"read"]*2)

    def test_lost_transfer_ack_reports_position_without_replaying(self):
        t=FakeTransport()
        original=t.write
        def write(data,timeout=2000):
            result=original(data,timeout)
            if isinstance(data,bytes):t.replies.clear()
            return result
        t.write=write
        with self.assertRaisesRegex(PrinterError,"bytes 0–511.*print start"):
            t.protocol().transfer(b"G1 X1\n"*100)
        self.assertEqual(len([x for x in t.writes if isinstance(x,bytes)]),1)
        self.assertNotIn("M33",t.commands())
        self.assertGreaterEqual(t.now,20)

    def test_heating_timeout(self):
        t=FakeTransport({"M105":"T:20 ok Q:0"})
        with self.assertRaises(PrinterError):t.protocol().heat(240,timeout=2)
        self.assertNotIn("M33",t.commands())

    def test_heating_reports_rising_temperature_and_completion(self):
        t=FakeTransport()
        readings=iter([20,100,190,210])
        original=t.write
        def write(data,timeout=2000):
            if data=="M105\n":t.overrides["M105"]="T:%g ok Q:0\n" % next(readings)
            return original(data,timeout)
        t.write=write;updates=[]
        t.protocol().heat(210,progress=lambda *args:updates.append(args))
        self.assertEqual(updates[0][:2],(20,210))
        self.assertEqual(updates[-1][:2],(210,210))
        self.assertEqual(len(updates),2)

    def test_busy_printer_is_not_overwritten(self):
        t=FakeTransport();t.printing=True
        with self.assertRaises(PrinterError):t.protocol().require_idle()
        self.assertNotIn("M30 ABCDE",t.commands())

    def test_usb_attach_does_not_reset_or_configure(self):
        from unittest.mock import MagicMock
        import usb.core
        import usb.util
        device=MagicMock();interface=MagicMock()
        device.get_active_configuration.return_value.__getitem__.return_value=interface
        out,inp=MagicMock(),MagicMock()
        with patch.object(usb.core,"find",side_effect=[[device],[]]),patch.object(usb.util,"find_descriptor",side_effect=[out,inp]):
            transport=UsbTransport()
            device.reset.assert_not_called();device.set_configuration.assert_not_called()
            transport.close()

    def test_usb_text_is_encoded_but_file_bytes_are_preserved(self):
        from unittest.mock import MagicMock
        t=UsbTransport.__new__(UsbTransport);t.core=MagicMock();t.output=MagicMock()
        t.output.write.side_effect=lambda data,timeout:len(data)
        t.write("G28\n");t.write(b"\x00\xff")
        self.assertEqual(t.output.write.call_args_list[0].args[0],b"G28\n")
        self.assertEqual(t.output.write.call_args_list[1].args[0],b"\x00\xff")

    def test_usb_read_sends_sdk_empty_packet_before_reading(self):
        from unittest.mock import MagicMock
        t=UsbTransport.__new__(UsbTransport);t.core=MagicMock()
        t.output,t.input=MagicMock(),MagicMock()
        t.output.write.return_value=0;t.input.read.return_value=b"tog\n"
        events=[]
        t.output.write.side_effect=lambda data,timeout:events.append(("write",data)) or len(data)
        t.input.read.side_effect=lambda size,timeout:events.append(("read",size)) or b"tog\n"
        self.assertEqual(t.read(),"tog\n")
        self.assertEqual(events,[("write",b""),("read",512)])


class WorkflowTests(unittest.TestCase):
    def job(self,text):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        p=Path(directory.name)/"test.gcode";p.write_text(text);return p

    def test_stage_preheat_uses_extrusion_target_not_last_layer(self):
        p=self.job("M104 S150\nG28\nM109 S215\nG1 X1 E1\nM104 S210\nG1 X2 E2\nM104 S0\n")
        data,report=prepare_job(p)
        self.assertEqual(report["target_c"],215)
        self.assertIn(b"M104 S210",data)
        self.assertEqual(p.read_text().splitlines()[0],"M104 S150")

    def test_metadata_and_pid_removed_from_prepared_copy(self):
        p=self.job("M31 A999 L999\nM130 T6 U1.3 V80\nG21\nM82\nM109 S210\nG1 E1\n")
        data,report=prepare_job(p)
        self.assertNotIn(b"M130",data);self.assertNotIn(b"G21",data)
        lines=data.decode().splitlines()
        self.assertIn("L%d" % len(lines),lines[0])
        self.assertIn("M130",p.read_text())

    def test_explicit_temperature_rewrites_active_targets_not_cooldown(self):
        p=self.job("M109 S215\nG1 E1\nM104 S210\nM104 S0\n")
        data,report=prepare_job(p,240)
        self.assertIn(b"M104 S240",data);self.assertIn(b"M104 S0",data)
        self.assertEqual(report["target_c"],240)

    def test_numbered_lowercase_job_is_normalized_before_temperature_override(self):
        p=self.job("N1 m109 s215*42\nN2 g1 e1*55\nN3 m104 s0*10\n")
        data,_=prepare_job(p,240)
        self.assertIn(b"M109 S240",data)
        self.assertIn(b"G1 E1",data)
        self.assertIn(b"M104 S0",data)
        self.assertNotIn(b"*",data)

    def test_heated_bed_and_relative_extrusion_rejected(self):
        for bad in ("M190 S60","M83","G20","M24"):
            with self.subTest(bad=bad):
                with self.assertRaises(PrinterError):prepare_job(self.job(bad+"\nM109 S210\nG1 E1\n"))

    def test_missing_temperature_requires_explicit_target(self):
        p=self.job("G28\nG1 E1\n")
        with self.assertRaises(PrinterError):prepare_job(p)
        self.assertEqual(prepare_job(p,210)[1]["target_c"],210)

    def test_failed_heat_cools_and_does_not_start(self):
        t=FakeTransport({"M105":"T:20 ok Q:0"})
        p=self.job("M109 S210\nG1 E1\n")
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(PrinterError):print_job(t.protocol(),p,heat_timeout=1)
        self.assertIn("M104 S0",t.commands());self.assertNotIn("M33",t.commands())

    def test_successful_print_transfer_then_heat_then_start(self):
        t=FakeTransport();p=self.job("M109 S210\nG1 E1\n")
        output=io.StringIO()
        with contextlib.redirect_stdout(output):print_job(t.protocol(),p)
        commands=t.commands()
        self.assertLess(commands.index("M30 ABCDE"),commands.index("M104 S210"))
        self.assertLess(commands.index("M104 S210"),commands.index("M33"))
        self.assertTrue(t.printing)
        text=output.getvalue()
        self.assertLess(text.index("Transfer complete. Heating"),text.index("Heating:"))
        self.assertLess(text.index("Heating:"),text.index("Nozzle ready. Starting"))
        self.assertIn("Print start confirmed",text)

    def test_calibration_absolute_jog_and_three_advances(self):
        t=FakeTransport();c=Calibration(t.protocol());c.start();c.jog(-.05)
        self.assertAlmostEqual(c.z,1.95)
        c.next();c.next();c.next()
        self.assertEqual(t.commands().count("G132"),3)
        self.assertIn("G1 Z1.95 F120",t.commands());self.assertNotIn("G91",t.commands())
        self.assertFalse(c.active);self.assertEqual(t.commands()[-2:], ["G28","M625"])

    def test_calibration_cancel_does_not_save_offset(self):
        t=FakeTransport();answers=iter(["u","q"])
        with contextlib.redirect_stdout(io.StringIO()):calibration(t.protocol(),ask=lambda _:next(answers))
        self.assertNotIn("G132",t.commands());self.assertIn("G28",t.commands())

    def test_calibration_rejects_out_of_range_and_late_jog(self):
        t=FakeTransport();c=Calibration(t.protocol());c.start()
        with self.assertRaises(PrinterError):c.jog(-3)
        c.next()
        with self.assertRaises(PrinterError):c.jog(-.05)

    def test_material_filament_waits_then_cools(self):
        t=FakeTransport()
        with contextlib.redirect_stdout(io.StringIO()):filament(t.protocol(),"unload",240)
        commands=t.commands()
        self.assertIn("M703 S240",commands)
        self.assertLess(commands.index("M703 S240"),commands.index("M702"))
        self.assertEqual(commands[-1],"M104 S0")

    def test_dry_run_never_opens_usb(self):
        p=self.job("M109 S210\nG1 E1\n")
        with patch("bee_cli.UsbTransport") as usb,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["print",str(p),"--dry-run"]),0)
            usb.assert_not_called()

    def test_monitor_bootloader_does_not_switch_modes(self):
        t=FakeTransport({"M625":"ok - Error: Bad M-code 625 ok Q:0"})
        with self.assertRaises(PrinterError):connect_printer(factory=lambda _:t)
        self.assertNotIn("M630",t.commands());self.assertTrue(t.closed)

    def test_action_can_start_firmware_and_reconnect(self):
        boot=FakeTransport({"M625":"ok - Error: Bad M-code 625 ok Q:0"})
        firmware=FakeTransport();devices=iter([boot,firmware])
        with contextlib.redirect_stdout(io.StringIO()):
            connected,_=connect_printer(allow_firmware_switch=True,factory=lambda _:next(devices),sleep=lambda _:None)
        self.assertIs(connected,firmware);self.assertIn("M630",boot.commands());self.assertTrue(boot.closed)

    def test_warm_nozzle_is_not_calibrated(self):
        t=FakeTransport();t.target=215
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(PrinterError):calibration(t.protocol())
        self.assertNotIn("G131 Z2",t.commands())


if __name__=="__main__":unittest.main()
