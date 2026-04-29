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

    # GSM-7 default alphabet table (3GPP TS 23.038)
    _GSM7 = (
        "@£$¥èéùìòÇ\nØø\rÅå"
        "ΔΦΓΛΩΠΨΣΘΞÆæßÉ"
        " !\"#¤%&'()*+,-./"
        "0123456789:;<=>?"
        "¡ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "ÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyz"
        "äöñüà"
    )
    # Correct full 128-char GSM7 table
    _GSM7_TABLE = (
        "@£$¥èéùìòÇ\nØø\rÅå"
        "\u0394_\u03a6\u0393\u039b\u03a9\u03a0\u03a8\u03a3\u0398\u039e\x1b\u00c6\u00e6\u00df\u00c9"
        " !\"#\u00a4%&'()*+,-./"
        "0123456789:;<=>?"
        "\u00a1ABCDEFGHIJKLMNOPQRSTUVWXYZ\u00c4\u00d6\u00d1\u00dc\u00a7"
        "\u00bfabcdefghijklmnopqrstuvwxyz\u00e4\u00f6\u00f1\u00fc\u00e0"
    )

    @staticmethod
    def _decode_gsm7(data):
        """Dekóduje GSM-7 bit-packed bajty na řetězec."""
        table = GSM._GSM7_TABLE
        buf, bits, chars = 0, 0, []
        for byte in data:
            buf |= byte << bits
            bits += 8
            while bits >= 7:
                idx = buf & 0x7F
                buf >>= 7
                bits -= 7
                if idx < len(table):
                    chars.append(table[idx])
                else:
                    chars.append("?")
        return "".join(chars).strip()

    def ussd(self, code, timeout=30):
        """
        Odešle USSD kód (např. '*101#') a vrátí odpověď operátora.

        SIM868 neodesílá +CUSD: prefix — po OK posílá rovnou raw data.
        Data jsou GSM-7 bit-packed (85 bajtů → ~97 znaků).
        """
        self._send('AT+CSCS="IRA"')
        time.sleep(0.3)
        self.ser.reset_input_buffer()
        self.ser.write(f'AT+CUSD=1,"{code}",15\r\n'.encode())
        buf = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.ser.in_waiting:
                buf += self.ser.read(self.ser.in_waiting)
            # Standardní +CUSD formát
            if b"+CUSD" in buf:
                return self._parse_cusd_bytes(buf)
            # Chyby modem posílá v ASCII
            ascii_view = buf.decode("ascii", errors="ignore")
            for err in ("+CME ERROR", "+CMS ERROR"):
                if err in ascii_view:
                    return "CHYBA modemu: " + ascii_view.strip()
            # SIM868 quirk: pošle OK + raw GSM-7 data bez +CUSD prefixu
            ok_idx = buf.find(b"\r\nOK\r\n")
            if ok_idx != -1:
                after_ok = buf[ok_idx + 6:]
                # Počkáme na konec přenosu (0.5 s ticho)
                if after_ok and time.time() > deadline - 25:
                    break
                if len(after_ok) > 10 and time.time() - (deadline - timeout) > 4:
                    break
            time.sleep(0.1)

        # Zkusíme standardní CUSD parsování
        if b"+CUSD" in buf:
            return self._parse_cusd_bytes(buf)

        # Quirk mode: extrahujeme data za OK a dekódujeme jako GSM-7
        ok_idx = buf.find(b"\r\nOK\r\n")
        if ok_idx != -1:
            raw_data = buf[ok_idx + 6:]
            if raw_data:
                # Zkusíme GSM-7
                try:
                    result = GSM._decode_gsm7(raw_data).strip()
                    if result and any(c.isalpha() for c in result):
                        return result
                except Exception:
                    pass
                # Zkusíme UCS2-BE (pokud sudý počet bajtů)
                if len(raw_data) % 2 == 0:
                    try:
                        return raw_data.decode("utf-16-be").strip()
                    except Exception:
                        pass
                # Fallback: latin-1
                return raw_data.decode("latin-1", errors="replace").strip()

        return "(žádná odpověď od operátora — zkus jiný USSD kód)"

    @staticmethod
    def _parse_cusd_bytes(buf):
        """
        Najde +CUSD v surovém byte bufferu a dekóduje obsah.
        Formát: +CUSD: <n>,"<data>",<dcs>
        """
        import re as _re
        idx = buf.find(b"+CUSD")
        if idx == -1:
            return buf.decode("utf-8", errors="replace").strip()
        chunk = buf[idx:]
        q_open = chunk.find(b'"')
        if q_open == -1:
            return chunk.decode("ascii", errors="replace").strip()
        content_raw = chunk[q_open + 1:]
        m = _re.search(rb'",\s*(\d+)', content_raw)
        if m:
            data_bytes = content_raw[:m.start()]
            dcs = int(m.group(1))
        else:
            data_bytes = content_raw
            dcs = 0
        # DCS 72 = UCS2-BE binárně
        if dcs == 72 or (len(data_bytes) % 2 == 0 and b"\x00" in data_bytes):
            try:
                return data_bytes.decode("utf-16-be")
            except Exception:
                pass
        # UCS2 hex
        try:
            text = data_bytes.decode("ascii").strip().strip('"')
            if len(text) % 4 == 0 and all(c in "0123456789ABCDEFabcdef" for c in text):
                return bytes.fromhex(text).decode("utf-16-be")
        except Exception:
            pass
        # GSM-7 nebo plain text
        try:
            return GSM._decode_gsm7(data_bytes).strip()
        except Exception:
            pass
        return data_bytes.decode("latin-1", errors="replace").strip()

    def enable_clip(self):
        """Zapne zobrazování čísla volajícího."""
        return self._send("AT+CLIP=1")

    def signal(self):
        return self._send("AT+CSQ")

    def close(self):
        self.ser.close()
