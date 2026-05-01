#!/usr/bin/env python3
"""
Naslouchá příchozím hovorům a SMS.

Hovory:
  1 - Přijmout hovor
  2 - Odmítnout hovor
  3 - Odmítnout a odeslat SMS (text z configu)

SMS:
  Při příchodu SMS se zobrazí odesílatel a text (včetně diakritiky).
  Při startu přečte i SMS uložené v paměti modemu ze dřívějška.

Použití: python3 incoming.py
"""

import time
import threading
from gsm import GSM, load_config
from led import LEDs
from buttons import Buttons


class IncomingCallListener:
    def __init__(self):
        self.cfg = load_config()
        self.gsm = GSM()
        self.leds = LEDs()
        self.led = self.leds.led1   # LED1 = hlavní (hovory/SMS)
        self.buttons = Buttons()
        self.buttons.on_hook_press    = self._hook_button_pressed
        self.buttons.on_button2_press = self._button2_pressed
        self._call_active = False
        self.gsm.enable_clip()
        self.gsm._send("AT+CMGF=1")          # textový režim SMS
        self.gsm._send('AT+CSCS="IRA"')      # ASCII charset — čitelný header
        # +CMTI: SMS uložena → přečteme přes AT+CMGR (spolehlivé, bez raw UCS2)
        # Místo +CMT přímé doručení (binární bordel) používáme index notifikaci
        self.gsm._send("AT+CNMI=2,1,0,0,0")
        self.ringing = False
        self.caller_number = "neznámé"
        self._read_stored_sms()

    # ── Pomocné metody ───────────────────────────────────────────────────────

    @staticmethod
    def _decode_sms_text(text):
        """Dekóduje UCS2 hex string (diakritika); jinak vrátí plain text."""
        t = text.strip()
        if len(t) % 4 == 0 and len(t) >= 4 and all(c in "0123456789ABCDEFabcdef" for c in t):
            try:
                return bytes.fromhex(t).decode("utf-16-be")
            except Exception:
                pass
        return t

    def _read_sms_by_index(self, index):
        """Přečte SMS na daném indexu přes AT+CMGR a vrátí (odesílatel, text)."""
        resp = self.gsm._send(f"AT+CMGR={index}", delay=1)
        lines = [l.strip() for l in resp.strip().splitlines() if l.strip()]
        sender, text = "?", ""
        for i, line in enumerate(lines):
            if line.startswith("+CMGR:"):
                try:
                    sender = line.split('"')[3]
                except IndexError:
                    pass
                if i + 1 < len(lines):
                    text = self._decode_sms_text(lines[i + 1])
                break
        return sender, text

    def _read_stored_sms(self):
        """Přečte všechny SMS uložené v paměti modemu/SIM."""
        resp = self.gsm._send('AT+CMGL="ALL"', delay=2)
        if not resp.strip() or "ERROR" in resp:
            return
        lines = resp.strip().splitlines()
        found = False
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("+CMGL:"):
                try:
                    sender = line.split('"')[3]
                except IndexError:
                    sender = "?"
                text = self._decode_sms_text(lines[i + 1].strip()) if i + 1 < len(lines) else ""
                if not found:
                    print("\n-- Uložené SMS v paměti modemu --")
                    found = True
                print(f"[SMS] Od: {sender}")
                print(f"      Text: {text}")
                i += 2
                continue
            i += 1
        if found:
            print("----------------------------------\n")

    # ── Obsluha tlačítek (GPIO interrupt → callback) ─────────────────────────

    def _hook_button_pressed(self):
        """HOOK tlačítko: zvedne nebo položí sluchátko."""
        if self.ringing:
            # zvonění → přijmout hovor
            print("\n[HOOK] Přijímám hovor...")
            self.gsm.answer()
            self.ringing = False
            self._call_active = True
            self.led.blink("call_active")
            print("Hovor přijat. Stiskni HOOK pro zavěšení.")
        elif self._call_active:
            # aktivní hovor → zavěsit
            print("\n[HOOK] Zavěšuji...")
            self.gsm.hangup()
            self._call_active = False
            self.led.off()
            print("\nNaslouchám... (Ctrl+C pro ukončení)")
        else:
            # klid → ignoruj (nebo budoucí použití)
            pass

    def _button2_pressed(self):
        """Tlačítko 2 — rezerva pro budoucí použití."""
        print("\n[BTN2] Tlačítko 2 stisknuto (zatím bez akce).")

    # ── Čtecí smyčka ────────────────────────────────────────────────────────

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

        # ── Příchozí SMS (index notifikace) ─────────────────────────────────
        if line.startswith("+CMTI:"):
            # +CMTI: "SM",3  nebo  +CMTI: "ME",3
            try:
                index = int(line.split(",")[-1].strip())
            except ValueError:
                return
            sender, text = self._read_sms_by_index(index)
            self.led.sms_flash()
            print(f"\n[SMS] Od: {sender}")
            print(f"      Text: {text}")
            print("\nNaslouchám... (Ctrl+C pro ukončení)")
            return

        # ── Příchozí hovor ───────────────────────────────────────────────────
        if line == "RING":
            if not self.ringing:
                self.ringing = True
                self.led.blink("ring")
                print(f"\nPříchozí hovor od: {self.caller_number}")
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
            if self.ringing or self._call_active:
                self.led.off()
                print(f"\nVolající zavěsil ({line}).")
                self.ringing = False
                self._call_active = False
                self.caller_number = "neznámé"
                print("\nNaslouchám... (Ctrl+C pro ukončení)")

        elif line not in ("OK", "ERROR"):
            # Debug — vypiš vše neznámé co modem pošle
            print(f"[modem] {line!r}")

    # ── Vstup od uživatele ───────────────────────────────────────────────────

    def _show_menu(self):
        print("  1 - Přijmout hovor")
        print("  2 - Odmítnout hovor")
        print("  3 - Odmítnout + odeslat SMS")
        print("Volba: ", end="", flush=True)

    def _handle_input(self):
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
                self._call_active = True
                self.led.blink("call_active")
                print("Hovor přijat. Stiskni Enter nebo HOOK tlačítko pro zavěšení.")
                input()
                self.gsm.hangup()
                self._call_active = False
                self.led.off()
                self.caller_number = "neznámé"
                print("\nNaslouchám... (Ctrl+C pro ukončení)")

            elif choice == "2":
                print("Odmítám hovor...")
                self.gsm.hangup()
                self.ringing = False
                self._call_active = False
                self.led.off()
                self.caller_number = "neznámé"
                print("\nNaslouchám... (Ctrl+C pro ukončení)")

            elif choice == "3":
                number = self.caller_number
                sms_text = self.cfg["sms"]["reject_message"]
                print("Odmítám hovor a odesílám SMS...")
                self.gsm.hangup()
                self.ringing = False
                self.led.off()
                self.caller_number = "neznámé"
                resp = self.gsm.send_sms(number, sms_text)
                if "+CMGS" in resp:
                    print(f"SMS odeslána na {number}.")
                else:
                    print("SMS se nepodařilo odeslat.")
                print("\nNaslouchám... (Ctrl+C pro ukončení)")

    # ── Hlavní smyčka ────────────────────────────────────────────────────────

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
            if self.ringing or self._call_active:
                self.gsm.hangup()
            self.buttons.cleanup()
            self.leds.cleanup()
            self.gsm.close()


def main():
    listener = IncomingCallListener()
    listener.run()


if __name__ == "__main__":
    main()
