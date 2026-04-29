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
        self.ringing = False
        self.caller_number = "neznámé"

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

    def _process_line(self, line):
        if not line:
            return

        if line == "RING":
            if not self.ringing:
                self.ringing = True
                print(f"\n📞 Příchozí hovor od: {self.caller_number}")
                self._show_menu()

        elif line.startswith("+CLIP:"):
            # +CLIP: "731164187",145,,,,0
            try:
                self.caller_number = line.split('"')[1]
                if self.ringing:
                    print(f"   Číslo: {self.caller_number}")
            except IndexError:
                pass

        elif line in ("NO CARRIER", "BUSY", "NO ANSWER"):
            if self.ringing:
                print(f"\nVolající zavěsil ({line}).")
                self.ringing = False
                self.caller_number = "neznámé"
                print("\nNaslouchám příchozím hovorům... (Ctrl+C pro ukončení)")

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
        print("Naslouchám příchozím hovorům... (Ctrl+C pro ukončení)")

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
