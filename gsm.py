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
        """ATD — odpověď chodí asynchronně (OK / NO CARRIER / BUSY …), nelze ji přečíst jedním _send."""
        num = "".join(number.split())
        self.ser.reset_input_buffer()
        self.ser.write(f"ATD{num};\r\n".encode())
        time.sleep(0.2)
        lines = self.read_lines(timeout=25)
        return "\n".join(lines) if lines else ""

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

    def answer(self):
        return self._send("ATA")

    def send_sms(self, number, text):
        self._send("AT+CMGF=1")  # textový režim
        self.ser.reset_input_buffer()
        self.ser.write(f'AT+CMGS="{number}"\r\n'.encode())
        time.sleep(0.5)
        self.ser.write((text + chr(26)).encode())  # Ctrl+Z = odeslat
        lines = self.read_lines(timeout=15)
        return "\n".join(lines) if lines else ""

    def enable_clip(self):
        """Zapne zobrazování čísla volajícího."""
        return self._send("AT+CLIP=1")

    def signal(self):
        return self._send("AT+CSQ")

    def close(self):
        self.ser.close()
