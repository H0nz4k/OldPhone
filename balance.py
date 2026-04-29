#!/usr/bin/env python3
"""
Zjistí stav kreditu — dvě metody:

1) SMS na 4603 (T-Mobile CZ, doporučeno — přijde zpět SMS s kreditem)
       python3 balance.py sms

2) USSD *101# (experimentální — SIM868 posílá raw bajty bez +CUSD: prefixu)
       python3 balance.py ussd

3) Raw debug — ukáže hex dump odpovědi modemu
       python3 balance.py debug
"""

import sys
import time
from gsm import GSM, load_config

MODE = sys.argv[1].lower() if len(sys.argv) > 1 else "sms"

# ── SMS metoda ─────────────────────────────────────────────────────────────
if MODE == "sms":
    print("Odesílám SMS s dotazem na kredit na 4603 (T-Mobile CZ)...")
    print("Odpověď přijde jako SMS zpět — spusť python3 incoming.py pro příjem.")
    gsm = GSM()
    resp = gsm.send_sms("4603", "KREDIT")
    gsm.close()
    r = resp.strip()
    if "+CMGS" in resp:
        print("SMS odeslána. Vyčkej na příchozí SMS s výší kreditu.")
    elif r:
        print(f"Odpověď modemu:\n{r}")
    else:
        print("Žádná odpověď od modemu.")

# ── USSD metoda ────────────────────────────────────────────────────────────
elif MODE == "ussd":
    USSD_CODE = sys.argv[2] if len(sys.argv) > 2 else "*101#"
    print(f"Odesílám USSD: {USSD_CODE}")
    gsm = GSM()
    result = gsm.ussd(USSD_CODE)
    gsm.close()
    print(f"\nOdpověď operátora:\n{result}")

# ── Debug hex dump ──────────────────────────────────────────────────────────
elif MODE == "debug":
    import serial
    cfg = load_config()["gsm"]
    ser = serial.Serial(cfg["port"], cfg["baud"], timeout=cfg.get("timeout", 1))
    time.sleep(1)
    ser.write(b"ATE0\r\n"); time.sleep(0.5); ser.read(ser.in_waiting)
    ser.write(b'AT+CSCS="IRA"\r\n'); time.sleep(0.5); ser.read(ser.in_waiting)
    ser.reset_input_buffer()
    USSD_CODE = sys.argv[2] if len(sys.argv) > 2 else "*101#"
    print(f'Odesílám AT+CUSD=1,"{USSD_CODE}",15')
    ser.write(f'AT+CUSD=1,"{USSD_CODE}",15\r\n'.encode())
    buf = b""
    deadline = time.time() + 35
    while time.time() < deadline:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            buf += chunk
            elapsed = round(35 - (deadline - time.time()), 1)
            print(f"[{elapsed}s] hex: {chunk.hex()}")
            print(f"       ascii: {chunk.decode('ascii', errors='replace')!r}")
        time.sleep(0.1)
    ser.close()
    print(f"\n--- Celý buffer ({len(buf)} B) ---")
    print(f"hex: {buf.hex()}")
    # Zkusíme různá dekódování
    ok_idx = buf.find(b"\r\nOK\r\n")
    if ok_idx != -1:
        raw = buf[ok_idx + 6:]
        print(f"\nData za OK ({len(raw)} B):")
        for enc in ("utf-8", "latin-1", "cp1250", "utf-16-be", "utf-16-le"):
            try:
                print(f"  {enc:12s}: {raw.decode(enc, errors='replace')!r}")
            except Exception:
                pass
        # GSM-7
        try:
            from gsm import GSM as _GSM
            gsm7 = _GSM._decode_gsm7(raw)
            print(f"  {'gsm7':12s}: {gsm7!r}")
        except Exception as e:
            print(f"  gsm7: chyba — {e}")

else:
    print(f"Neznámý režim '{MODE}'. Použi: sms | ussd | debug")
    sys.exit(1)
