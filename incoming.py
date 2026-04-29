#!/usr/bin/env python3
"""
Naslouchá příchozím hovorům.
Zobrazí číslo volajícího a nabídne volby:
  1 - Přijmout hovor
  2 - Odmítnout hovor
  3 - Odmítnout a odeslat SMS (text z configu)

Použití: python3 incoming.py
"""

import sys
import time
import threading
import serial
from gsm import GSM, load_config


class IncomingCallListener:
    def __init__(self):
        self.cfg = load_config()
        self.gsm = GSM()
        self.gsm.enable_clip()
        self.gsm._send("AT+CMGF=1")          # textový režim
        self.gsm._send('AT+CSCS="IRA"')      # ASCII charset pro čitelný +CMT header
        self.gsm._send("AT+CNMI=2,2,0,0,0")  # příchozí SMS → okamžitě jako +CMT URC
        self.ringing = False
        self.caller_number = "neznámé"
        self._pending_sms_sender = None       # čekáme na text SMS po +CMT hlavičce
        self._read_stored_sms()

    def _read_stored_sms(self):
        """Přečte SMS uložené v paměti modemu/SIM (přišly před spuštěním skriptu)."""
        resp = self.gsm._send('AT+CMGL="ALL"', delay=2)
        if not resp.strip() or "ERROR" in resp:
            return
        lines = resp.strip().splitlines()
        i = 0
        found = False
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("+CMGL:"):
                # +CMGL: <index>,"REC UNREAD","číslo",,"datum"
                try:
                    sender = line.split('"')[3]
                except IndexError:
                    sender = "?"
                if i + 1 < len(lines):
                    text = self._decode_sms_text(lines[i + 1].strip())
                    if not found:
                        print("\n-- Uložené SMS v paměti modemu --")
                        found = True
                    print(f"[SMS] Od: {sender}  Text: {text}")
                    i += 2
                    continue
            i += 1
        if found:
            print("----------------------------------\n")

    def _read_loop(self):
        """Čte sériový port v samostatném vlákně."""
        buffer = ""
        while self.running:
            if self.gsm.ser.in_waiting:
                chunk = self.gsm.ser.read(self.gsm.ser.in_waiting).decode(errors="ignore")
                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines[-1]
                for line in lines[:-1]:
                    self._process_line(line.strip())
            time.sleep(0.05)

    @staticmethod
    def _decode_sms_text(text):
        """Pokusí se dekódovat UCS2 hex text SMS, jinak vrátí tak jak je."""
        t = text.strip()
        if len(t) % 4 == 0 and len(t) >= 4 and all(c in "0123456789ABCDEFabcdef" for c in t):
            try:
                return bytes.fromhex(t).decode("utf-16-be")
            except Exception:
                pass
        return t

    def _process_line(self, line):
        if not line:
            return

        # ── Příchozí SMS ────────────────────────────────────────────────
        if line.startswith("+CMT:"):
            # +CMT: "+420731164187","","26/04/30,01:00:00+08"
            try:
                self._pending_sms_sender = line.split('"')[1]
            except IndexError:
                self._pending_sms_sender = "neznámé"
            return   # text SMS přijde na dalším řádku

        if self._pending_sms_sender is not None:
            sender = self._pending_sms_sender
            self._pending_sms_sender = None
            text = self._decode_sms_text(line)
            print(f"\n[SMS] Od: {sender}")
            print(f"      Text: {text}")
            print("\nNaslouchám... (Ctrl+C pro ukončení)")
            return

        # ── Příchozí hovor ───────────────────────────────────────────────
        if line == "RING":
            if not self.ringing:
                self.ringing = True
                print(f"\nPrichozi hovor od: {self.caller_number}")
                self._show_menu()

        elif line.startswith("+CLIP:"):
            # +CLIP: "731164187",145,,,,0
            try:
                self.caller_number = line.split('"')[1]
                if self.ringing:
                    print(f"   Cislo: {self.caller_number}")
            except IndexError:
                pass

        elif line in ("NO CARRIER", "BUSY", "NO ANSWER"):
            if self.ringing:
                print(f"\nVolající zavěsil ({line}).")
                self.ringing = False
                self.caller_number = "neznámé"
                print("\nNaslouchám... (Ctrl+C pro ukončení)")

        elif line not in ("OK", "ERROR", "AT"):
            # Debug: vypiš vše co modem pošle a my neznáme
            print(f"[modem] {line!r}")

    def _show_menu(self):
        print("  1 - Přijmout hovor")
        print("  2 - Odmítnout hovor")
        print("  3 - Odmítnout + odeslat SMS")
        print("Volba: ", end="", flush=True)

    def _handle_input(self):
        """Zpracovává vstup od uživatele v samostatném vlákně."""
        while self.running:
            try:
                choice = input()
            except EOFError:
                break

            if not self.ringing and choice not in ("1", "2", "3"):
                continue

            if choice == "1":
                print("Přijímám hovor...")
                self.gsm.answer()
                self.ringing = False
                print("Hovor přijat. Stiskni Enter pro zavěšení.")
                input()
                self.gsm.hangup()
                self.ringing = False
                self.caller_number = "neznámé"
                print("\nNaslouchám příchozím hovorům... (Ctrl+C pro ukončení)")

            elif choice == "2":
                print("Odmítám hovor...")
                self.gsm.hangup()
                self.ringing = False
                self.caller_number = "neznámé"
                print("\nNaslouchám příchozím hovorům... (Ctrl+C pro ukončení)")

            elif choice == "3":
                number = self.caller_number
                sms_text = self.cfg["sms"]["reject_message"]
                print("Odmítám hovor a odesílám SMS...")
                self.gsm.hangup()
                self.ringing = False
                self.caller_number = "neznámé"
                resp = self.gsm.send_sms(number, sms_text)
                if "+CMGS" in resp:
                    print(f"SMS odeslána na {number}.")
                else:
                    print("SMS se nepodařilo odeslat.")
                print("\nNaslouchám příchozím hovorům... (Ctrl+C pro ukončení)")

    def run(self):
        self.running = True
        print("Naslouchám příchozím hovorům a SMS... (Ctrl+C pro ukončení)")

        reader = threading.Thread(target=self._read_loop, daemon=True)
        handler = threading.Thread(target=self._handle_input, daemon=True)
        reader.start()
        handler.start()

        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nUkončuji...")
        finally:
            self.running = False
            if self.ringing:
                self.gsm.hangup()
            self.gsm.close()


def main():
    listener = IncomingCallListener()
    listener.run()


if __name__ == "__main__":
    main()
