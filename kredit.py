#!/usr/bin/env python3
"""
Zjistí kredit T-Mobile CZ přes SMS na 4603 a uloží historii do kredit.csv.

Použití: python3 kredit.py
"""

import csv
import os
import re
import time
from datetime import datetime
from gsm import GSM

CSV_FILE = os.path.join(os.path.dirname(__file__), "kredit.csv")
CSV_HEADER = ["datum", "kredit_kc", "bonus_kc", "platnost", "zprava"]


# ── Parsování SMS ────────────────────────────────────────────────────────────

def parse_kredit(text):
    """
    Z textu SMS od T-Mobile CZ vytáhne:
      - kredit_kc  (hlavní kredit)
      - bonus_kc   (bonusový kredit, pokud je)
      - platnost   (datum platnosti)
    Vrátí dict nebo None pokud parsování selže.
    """
    t = text.upper()

    kredit = None
    m = re.search(r'ZUSTATEK KREDITU\s+([\d,\.]+)\s*KC', t)
    if m:
        kredit = m.group(1).replace(",", ".")

    bonus = None
    m = re.search(r'BONUSOV[YÝ]\s+KREDIT\s+([\d,\.]+)\s*KC', t)
    if m:
        bonus = m.group(1).replace(",", ".")

    platnost = None
    m = re.search(r'PLATNY DO\s+(\d{1,2}\.\d{1,2}\.\d{4})', t)
    if m:
        platnost = m.group(1)

    if kredit is None:
        return None
    return {"kredit_kc": kredit, "bonus_kc": bonus or "", "platnost": platnost or ""}


# ── CSV ──────────────────────────────────────────────────────────────────────

def save_to_csv(kredit_kc, bonus_kc, platnost, zprava):
    """Uloží záznam do kredit.csv (vytvoří soubor pokud neexistuje)."""
    novy = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if novy:
            writer.writeheader()
        writer.writerow({
            "datum":     datetime.now().strftime("%Y-%m-%d %H:%M"),
            "kredit_kc": kredit_kc,
            "bonus_kc":  bonus_kc,
            "platnost":  platnost,
            "zprava":    zprava.replace("\n", " "),
        })
    print(f"Uloženo do {CSV_FILE}")


def show_history():
    """Zobrazí posledních 10 záznamů z kredit.csv."""
    if not os.path.exists(CSV_FILE):
        return
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    print("\n── Historie kreditu ──────────────────────────────")
    print(f"{'Datum':<17} {'Kredit':>8} {'Bonus':>8}  {'Platnost'}")
    print("─" * 50)
    for r in rows[-10:]:
        kc  = f"{r['kredit_kc']} Kč" if r['kredit_kc'] else "?"
        bon = f"{r['bonus_kc']} Kč"  if r['bonus_kc']  else "—"
        print(f"{r['datum']:<17} {kc:>8} {bon:>8}  {r['platnost']}")
    print("─" * 50)


# ── SMS čtení ────────────────────────────────────────────────────────────────

def decode_sms(raw):
    """Pokusí se dekódovat UCS2 hex, jinak vrátí plain text."""
    t = raw.strip()
    if len(t) % 4 == 0 and len(t) >= 4 and all(c in "0123456789ABCDEFabcdef" for c in t):
        try:
            return bytes.fromhex(t).decode("utf-16-be")
        except Exception:
            pass
    return t


def read_sms_by_index(gsm, index):
    """Přečte SMS na daném indexu přes AT+CMGR."""
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
                text = decode_sms(lines[i + 1])
            break
    return sender, text


def process_sms(sender, text):
    """Zpracuje SMS od T-Mobile: vypíše kredit a uloží do CSV."""
    print(f"\nOdpověď T-Mobile:\nOd: {sender}\n{text}\n")
    parsed = parse_kredit(text)
    if parsed:
        kc  = parsed["kredit_kc"]
        bon = parsed["bonus_kc"]
        pl  = parsed["platnost"]
        print(f"  Kredit:  {kc} Kč")
        if bon:
            print(f"  Bonus:   {bon} Kč")
        if pl:
            print(f"  Platný do: {pl}")
        save_to_csv(kc, bon, pl, text)
    else:
        print("  (Nepodařilo se vytáhnout částku — ukládám celý text)")
        save_to_csv("", "", "", text)


# ── Hlavní logika ────────────────────────────────────────────────────────────

def main():
    show_history()

    gsm = GSM()

    # Zkontrolujeme uložené SMS — možná odpověď od 4603 už čeká v paměti
    resp = gsm._send('AT+CMGL="ALL"', delay=2)
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
            text = decode_sms(raw_text)
            if "4603" in sender and ("KC" in text.upper() or "KREDIT" in text.upper()):
                process_sms(sender, text)
                gsm.close()
                return
        i += 1

    # Pošleme SMS s dotazem
    print("Odesílám SMS 'KREDIT S' na 4603...")
    gsm.send_sms("4603", "KREDIT S")
    print("SMS odeslána. Čekám na odpověď T-Mobile (max 90 s)...\n")

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
                idx_lines = [l for l in buf.splitlines() if "+CMTI:" in l]
                if idx_lines:
                    try:
                        sms_idx = int(idx_lines[-1].split(",")[-1].strip())
                    except ValueError:
                        time.sleep(0.1)
                        continue
                    time.sleep(0.3)
                    sender, text = read_sms_by_index(gsm, sms_idx)
                    process_sms(sender, text)
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
