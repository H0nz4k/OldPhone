#!/usr/bin/env python3
"""
Pošle SMS na 4603 (T-Mobile CZ: dotaz na kredit) a čeká na odpověď SMS.
Používá jedno GSM spojení — nevzniká konflikt na sériovém portu.

Použití: python3 kredit.py
"""

import time
import threading
from gsm import GSM


def main():
    gsm = GSM()

    # 1) Pošleme dotaz
    print("Odesílám SMS na 4603...")
    resp = gsm.send_sms("4603", "KREDIT")
    if "+CMGS" in resp:
        print("SMS odeslána. Čekám na odpověď od T-Mobile (max 60 s)...\n")
    else:
        print(f"Varování — SMS odpověď modemu: {resp.strip() or '(prázdná)'}")
        print("Přesto čekám na příchozí SMS...\n")

    # 2) Čteme sériový port a hledáme příchozí SMS (+CMT nebo +CMTI)
    gsm._send("AT+CNMI=2,2,0,0,0")   # okamžité doručení SMS do terminálu (+CMT)
    gsm.ser.reset_input_buffer()

    buf = ""
    deadline = time.time() + 90       # max 90 s čekání
    answered = threading.Event()

    def read_loop():
        nonlocal buf
        while not answered.is_set() and time.time() < deadline:
            if gsm.ser.in_waiting:
                chunk = gsm.ser.read(gsm.ser.in_waiting).decode(errors="ignore")
                buf += chunk
                lines = buf.split("\n")
                buf = lines[-1]
                for line in lines[:-1]:
                    line = line.strip()
                    if not line:
                        continue
                    # +CMT: "<číslo>","","datum"   (text mode s UCS2 nebo IRA)
                    if line.startswith("+CMT:"):
                        # Příchozí SMS — číselník uložen, text přijde na dalším řádku
                        pass
                    elif buf_has_cmt_sender and line:
                        # Zobrazíme text SMS
                        display_sms(line)
                        answered.set()
            time.sleep(0.05)

    # Jednodušší přístup: sbíráme vše do bufferu a hledáme +CMT blok
    print("(Stiskni Ctrl+C pro ukončení)")
    try:
        while time.time() < deadline:
            if gsm.ser.in_waiting:
                chunk = gsm.ser.read(gsm.ser.in_waiting).decode(errors="ignore")
                buf += chunk

            # Hledáme blok +CMT
            if "+CMT:" in buf:
                idx = buf.index("+CMT:")
                after = buf[idx:]
                # Formát: +CMT: "číslo",..."datum"\r\ntext zprávy\r\n
                lines = after.split("\n")
                if len(lines) >= 2:
                    header = lines[0].strip()
                    sms_text = lines[1].strip()
                    if sms_text:
                        # Pokus o dekódování UCS2 hex (pokud obsahuje jen hex znaky)
                        decoded = try_decode(sms_text)
                        print(f"Odpověď T-Mobile:\n{decoded}")
                        break

            time.sleep(0.1)
        else:
            print("Timeout — žádná odpověď nepřišla do 90 s.")
            print("Zkus: python3 incoming.py (pro manuální příjem SMS)")

    except KeyboardInterrupt:
        print("\nPřerušeno.")
    finally:
        gsm.close()


def try_decode(text):
    """Pokusí se dekódovat UCS2 hex string, jinak vrátí text beze změny."""
    t = text.strip()
    if len(t) % 4 == 0 and all(c in "0123456789ABCDEFabcdef" for c in t):
        try:
            return bytes.fromhex(t).decode("utf-16-be")
        except Exception:
            pass
    return t


if __name__ == "__main__":
    main()
