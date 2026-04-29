#!/usr/bin/env python3
"""
Zjistí stav kreditu přes USSD.
T-Mobile CZ: *101#  (výchozí)

Použití:
    python3 balance.py           # T-Mobile *101#
    python3 balance.py "*101#"   # explicitní kód
"""

import sys
from gsm import GSM

USSD_CODE = sys.argv[1] if len(sys.argv) > 1 else "*101#"

print(f"Odesílám USSD: {USSD_CODE}")
gsm = GSM()
result = gsm.ussd(USSD_CODE)
gsm.close()

print(f"\nOdpověď operátora:\n{result}")
