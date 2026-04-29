#!/usr/bin/env python3
"""
Zjistí stav kreditu přes USSD.
T-Mobile CZ: *101#  (výchozí)

Použití:
    python3 balance.py              # T-Mobile *101#
    python3 balance.py "*101#"      # explicitní kód
    python3 balance.py debug        # raw debug — ukáže přesné bajty z modemu
"""

import sys
import time
from gsm import GSM, load_config

DEBUG = "debug" in sys.argv
USSD_CODE = next((a for a in sys.argv[1:] if a != "debug"), "*101#")

if DEBUG:
    # Přímé čtení sériového portu bez parsování — ukážeme hex dump
    cfg = load_config()["gsm"]
    import serial
    ser = serial.Serial(cfg["port"], cfg["baud"], timeout=cfg.get("timeout", 1))
    time.sleep(1)
    ser.write(b'ATE0\r\n'); time.sleep(0.5); ser.read(ser.in_waiting)
    ser.write(b'AT+CSCS="IRA"\r\n'); time.sleep(0.5); ser.read(ser.in_waiting)
    ser.reset_input_buffer()
    print(f"Odesílám AT+CUSD=1,\"{USSD_CODE}\",15")
    ser.write(f'AT+CUSD=1,"{USSD_CODE}",15\r\n'.encode())
    buf = b""
    deadline = time.time() + 35
    while time.time() < deadline:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            buf += chunk
            elapsed = round(35 - (deadline - time.time()), 1)
            print(f"[{elapsed}s] hex: {chunk.hex()} | ascii: {chunk.decode('ascii', errors='replace')!r}")
        time.sleep(0.1)
    ser.close()
    print(f"\n--- Celý buffer ({len(buf)} B) ---")
    print(f"hex: {buf.hex()}")
    print(f"utf8: {buf.decode('utf-8', errors='replace')!r}")
else:
    print(f"Odesílám USSD: {USSD_CODE}")
    gsm = GSM()
    result = gsm.ussd(USSD_CODE)
    gsm.close()
    print(f"\nOdpověď operátora:\n{result}")
