import serial
import time
import yaml


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class GSM:
    def __init__(self, config_path="config.yaml"):
        cfg = load_config(config_path)["gsm"]
        self.ser = serial.Serial(
            cfg["port"],
            cfg["baud"],
            timeout=cfg.get("timeout", 1)
        )
        time.sleep(1)
        self._send("ATE0")  # vypni echo modulu
        self._call_rx_rest = ""

    def _send(self, cmd, delay=0.5):
        self.ser.write((cmd + "\r\n").encode())
        time.sleep(delay)
        return self.ser.read(self.ser.in_waiting).decode(errors="ignore")

    def read_lines(self, timeout=10):
        """Čte řádky ze sériového portu po dobu timeout sekund."""
        lines = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.ser.in_waiting:
                raw = self.ser.read(self.ser.in_waiting).decode(errors="ignore")
                for line in raw.splitlines():
                    line = line.strip()
                    if line:
                        lines.append(line)
            time.sleep(0.1)
        return lines

    def call(self, number):
        """
        ATD — čte jen do prvního řádku OK (= příkaz vytáčení přijat).
        NO CARRIER po skutečném hovoru nesmí skončit v této odpovědi, jinak call.py
        hlásí falešné selhání; zbytek bufferu předá wait_for_call_end().
        """
        num = "".join(number.split())
        self.ser.reset_input_buffer()
        self._call_rx_rest = ""
        self.ser.write(f"ATD{num};\r\n".encode())
        time.sleep(0.2)
        buf = ""
        out_lines = []
        deadline = time.time() + 45
        while time.time() < deadline:
            if self.ser.in_waiting:
                buf += self.ser.read(self.ser.in_waiting).decode(errors="ignore")
            while True:
                sep_len = 0
                cut = None
                if "\r\n" in buf:
                    cut = buf.index("\r\n")
                    sep_len = 2
                elif "\n" in buf:
                    cut = buf.index("\n")
                    sep_len = 1
                elif "\r" in buf:
                    cut = buf.index("\r")
                    sep_len = 1
                else:
                    break
                line = buf[:cut].strip()
                buf = buf[cut + sep_len :]
                if not line:
                    continue
                out_lines.append(line)
                up = line.upper()
                if up == "OK":
                    self._call_rx_rest = buf
                    return "\n".join(out_lines)
                if any(x in up for x in ("BUSY", "NO DIALTONE", "+CME ERROR")):
                    self._call_rx_rest = buf
                    return "\n".join(out_lines)
                if "NO CARRIER" in up:
                    self._call_rx_rest = buf
                    return "\n".join(out_lines)
            time.sleep(0.05)
        self._call_rx_rest = buf
        return "\n".join(out_lines) if out_lines else ""

    def modem_smoke_test(self):
        """Krátká kontrola spojení s modulem (pro ladění)."""
        self.ser.reset_input_buffer()
        out = []
        for cmd in ("AT", "AT+CSQ", "AT+CREG?", "AT+COPS?"):
            self.ser.write((cmd + "\r\n").encode())
            time.sleep(0.5)
            chunk = self.ser.read(self.ser.in_waiting).decode(errors="ignore")
            if chunk.strip():
                out.append(chunk.strip())
        return "\n".join(out)

    def hangup(self):
        return self._send("ATH")

    def wait_for_call_end(self, max_seconds=7200):
        """
        Po úspěšném ATD čte URC z linky. Při zavěšení vzdálenou stranou nebo odmítnutí
        hovoru modul typicky pošle NO CARRIER nebo NO ANSWER (záleží na operátorovi).
        """
        buf = ""
        end_needles = (
            "NO CARRIER",
            "NO ANSWER",
            "BUSY",
            "NO DIALTONE",
            "+CME ERROR",
        )
        deadline = time.time() + max_seconds
        buf = (getattr(self, "_call_rx_rest", None) or "") + buf
        self._call_rx_rest = ""
        while time.time() < deadline:
            if self.ser.in_waiting:
                buf += self.ser.read(self.ser.in_waiting).decode(errors="ignore")
            while True:
                sep_len = 0
                cut = None
                if "\r\n" in buf:
                    cut = buf.index("\r\n")
                    sep_len = 2
                elif "\n" in buf:
                    cut = buf.index("\n")
                    sep_len = 1
                elif "\r" in buf:
                    cut = buf.index("\r")
                    sep_len = 1
                else:
                    break
                line = buf[:cut].strip()
                buf = buf[cut + sep_len :]
                if not line:
                    continue
                upper = line.upper()
                for needle in end_needles:
                    if needle in upper:
                        return needle
            time.sleep(0.05)
        return "TIMEOUT"

    def answer(self):
        return self._send("ATA")

    def send_sms(self, number, text):
        self._send("AT+CMGF=1")       # textový režim
        self._send('AT+CSCS="UCS2"')  # UCS2 pro plnou podporu diakritiky

        # Číslo zůstává v ASCII; text kódujeme jako UCS2 hex
        ucs2_text = text.encode("utf-16-be").hex().upper()

        self.ser.reset_input_buffer()
        self.ser.write(f'AT+CMGS="{number}"\r\n'.encode())

        # Čekáme na výzvu '>' od modemu
        deadline = time.time() + 5
        prompt_ok = False
        buf = ""
        while time.time() < deadline:
            if self.ser.in_waiting:
                buf += self.ser.read(self.ser.in_waiting).decode(errors="ignore")
                if ">" in buf:
                    prompt_ok = True
                    break
            time.sleep(0.05)

        if not prompt_ok:
            return "ERROR: no prompt from modem"

        # Odešleme UCS2 text + Ctrl+Z
        self.ser.write((ucs2_text + chr(26)).encode())
        lines = self.read_lines(timeout=20)
        return "\n".join(lines) if lines else ""

    def enable_clip(self):
        """Zapne zobrazování čísla volajícího."""
        return self._send("AT+CLIP=1")

    def signal(self):
        return self._send("AT+CSQ")

    def close(self):
        self.ser.close()
