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
    r = resp.strip()
    if r:
        print(f"Odpověď modulu:\n{r}")
    else:
        print("Odpověď modulu:\n(prázdné — port/baud, napájení HAT, anténa)")
        print('Tip: python3 -c "from gsm import GSM; g=GSM(); print(g.modem_smoke_test()); g.close()"')

    up = r.upper()
    fail = any(
        x in up
        for x in (
            "NO CARRIER",
            "BUSY",
            "NO DIALTONE",
            "+CME ERROR",
            "+CMS ERROR",
        )
    ) or ("ERROR" in up and "OK" not in up)
    if fail or not r:
        print("Hovor pravděpodobně neproběhl — zkontroluj výše uvedenou odpověď a registraci v síti.")
        gsm.close()
        sys.exit(1)

    print("Modul přijal vytáčení. Stiskni Ctrl+C pro zavěšení.")

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
