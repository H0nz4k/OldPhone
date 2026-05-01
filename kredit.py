#!/usr/bin/env python3
"""
Pošle SMS na 4603 (T-Mobile CZ: dotaz na kredit) a čeká na odpověď SMS.
Používá jedno GSM spojení — nevzniká konflikt na sériovém portu.

Použití: python3 kredit.py
"""

import time
from gsm import GSM


def read_sms_by_index(gsm, index):
    """Přečte SMS na daném indexu, vrátí (odesílatel, text)."""
    resp = gsm._send(f"AT+CMGR={index}", delay=1)
    lines = [l.strip() for l in resp.strip().splitlines() if l.strip()]
    sender, text = "?", ""
    for i, line in enumerate(lines):
        if line.startswith("+CMGR:"):
            try:
                sender = line.split('"')[3]
            except IndexError:
                pass
            if i + 1 < len(lines):
                raw = lines[i + 1].strip()
                # Pokus o dekódování UCS2 hex (diakritika)
                if (len(raw) % 4 == 0 and len(raw) >= 4
                        and all(c in "0123456789ABCDEFabcdef" for c in raw)):
                    try:
                        text = bytes.fromhex(raw).decode("utf-16-be")
                        return sender, text
                    except Exception:
                        pass
                text = raw
            break
    return sender, text


def main():
    gsm = GSM()

    # Zkontrolujeme uložené SMS — možná odpověď od 4603 už čeká
    resp = gsm._send('AT+CMGL="ALL"', delay=2)
    stored = []
    lines = resp.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("+CMGL:"):
            try:
                sender = line.split('"')[3]
            except IndexError:
                sender = "?"
            raw_text = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if (len(raw_text) % 4 == 0 and len(raw_text) >= 4
                    and all(c in "0123456789ABCDEFabcdef" for c in raw_text)):
                try:
                    raw_text = bytes.fromhex(raw_text).decode("utf-16-be")
                except Exception:
                    pass
            stored.append((sender, raw_text))
            i += 2
            continue
        i += 1

    for sender, text in stored:
        if "4603" in sender or "kredit" in text.lower() or "kc" in text.lower():
            print(f"\nOdpověď T-Mobile (z paměti):\nOd: {sender}\n{text}\n")
            gsm.close()
            return

    # Pošleme SMS s dotazem — T-Mobile CZ vyžaduje "KREDIT S"
    print("Odesílám SMS 'KREDIT S' na 4603...")
    resp = gsm.send_sms("4603", "KREDIT S")
    if "+CMGS" in resp or resp.strip():
        print("SMS odeslána. Čekám na odpověď T-Mobile (max 90 s)...\n")
    else:
        print("Varování: prázdná odpověď modemu, přesto čekám...\n")

    # Přepneme na CMTI — oznámení indexu, pak přečteme přes CMGR
    gsm._send("AT+CNMI=2,1,0,0,0")
    gsm.ser.reset_input_buffer()
    buf = ""
    deadline = time.time() + 90

    print("(Stiskni Ctrl+C pro ukončení)")
    try:
        while time.time() < deadline:
            if gsm.ser.in_waiting:
                buf += gsm.ser.read(gsm.ser.in_waiting).decode(errors="ignore")

            if "+CMTI:" in buf:
                idx_line = [l for l in buf.splitlines() if "+CMTI:" in l]
                if idx_line:
                    try:
                        sms_idx = int(idx_line[-1].split(",")[-1].strip())
                    except ValueError:
                        time.sleep(0.1)
                        continue
                    time.sleep(0.3)   # krátká pauza než modem uloží
                    sender, text = read_sms_by_index(gsm, sms_idx)
                    print(f"\nOdpověď T-Mobile:\nOd: {sender}\n{text}\n")
                    break
            time.sleep(0.1)
        else:
            print("Timeout — žádná odpověď nepřišla do 90 s.")

    except KeyboardInterrupt:
        print("\nPřerušeno.")
    finally:
        gsm._send("AT+CNMI=0,0,0,0,0")
        gsm.close()


if __name__ == "__main__":
    main()
