#!/usr/bin/env python3
"""
Zavolá na číslo definované v config.yaml.
Použití: python3 call.py
         python3 call.py 777123456   (přepíše číslo z configu)
"""

import sys
import time
from gsm import GSM, load_config


def main():
    cfg = load_config()
    number = sys.argv[1] if len(sys.argv) > 1 else cfg["call"]["number"]

    print(f"Vytáčím: {number}")
    gsm = GSM()

    resp = gsm.call(number)
    print(f"Odpověď modulu: {resp.strip()}")
    print("Hovor zahájen. Stiskni Ctrl+C pro zavěšení.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nZavěšuji...")
        gsm.hangup()
        print("Hovor ukončen.")
    finally:
        gsm.close()


if __name__ == "__main__":
    main()
