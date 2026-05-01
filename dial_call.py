#!/usr/bin/env python3
"""
Volání pomocí rotačního ciferníku.

Logika:
  1. Spustíš skript → čeká na první číslici
  2. Točíš ciferníkem → číslo se skládá a zobrazuje
  3. Po 3 s ticha (žádná další číslice) → automaticky zavolá
  4. Hovor probíhá → Ctrl+C pro zavěšení

LED signalizace:
  LED1 (červená) — bliká "dial"        při zadávání čísla
  LED1 (červená) — bliká "call_active" během hovoru

Použití:
  python3 dial_call.py          # čeká na ciferník
  python3 dial_call.py 737xxx   # přeskočí ciferník, rovnou zavolá
"""

import sys
import time
from gsm import GSM, load_config
from led import LEDs
from cifernik import Cifernik

# Po kolika sekundách ticha se číslo odešle
DIAL_TIMEOUT = 3.0

# Minimální počet číslic před vytočením
MIN_DIGITS = 5


def read_number_from_dial(leds) -> str:
    """
    Čte číslice z ciferníku dokud nepřijde DIAL_TIMEOUT sekund ticha.
    Vrátí vytočené číslo jako string.
    """
    c = Cifernik()
    digits = []

    print("Vytáčej číslo ciferníkem...")
    print(f"(Po {DIAL_TIMEOUT} s ticha se automaticky zavolá)\n")

    leds.led1.blink("dial")

    try:
        while True:
            # První číslice — čekáme déle
            timeout = 30.0 if not digits else DIAL_TIMEOUT
            digit = c.read_digit(timeout=timeout)

            if digit is None:
                # Timeout
                if len(digits) >= MIN_DIGITS:
                    break   # dost číslic → voláme
                elif digits:
                    print(f"\n[!] Krátké číslo ({len(digits)} číslic), čekám dál...")
                    continue
                else:
                    print("\n(timeout — žádné číslo nezadáno)")
                    break
            else:
                digits.append(str(digit))
                number_so_far = "".join(digits)
                print(f"  [{digit}]  →  {number_so_far}", flush=True)

    except KeyboardInterrupt:
        print()
    finally:
        c.cleanup()

    return "".join(digits)


def make_call(number: str, leds):
    """Zavolá na číslo a čeká na konec hovoru."""
    print(f"\nVytáčím: {number}")
    leds.led1.blink("dial")

    gsm = GSM()
    resp = gsm.call(number)
    r = resp.strip()

    if r:
        print(f"Odpověď modulu: {r}")

    up = r.upper()
    fail = any(x in up for x in (
        "NO CARRIER", "BUSY", "NO DIALTONE", "+CME ERROR", "+CMS ERROR"
    )) or ("ERROR" in up and "OK" not in up)

    if fail or not r:
        leds.led1.off()
        print("Hovor neproběhl — zkontroluj signál a SIM kartu.")
        gsm.close()
        return

    print("Voláme... (Ctrl+C pro zavěšení)")
    leds.led1.blink("call_active")

    try:
        reason = gsm.wait_for_call_end()
        print(f"\nHovor ukončen: {reason}")
    except KeyboardInterrupt:
        print("\nZavěšuji...")
    finally:
        gsm.hangup()
        leds.led1.off()
        print("Zavěšeno.")
        gsm.close()


def main():
    leds = LEDs()

    try:
        # Číslo z příkazové řádky → přeskočíme ciferník
        if len(sys.argv) > 1:
            number = sys.argv[1]
            print(f"Číslo z příkazové řádky: {number}")
        else:
            number = read_number_from_dial(leds)

        if not number:
            print("Žádné číslo nezadáno — končím.")
            return

        if len(number) < MIN_DIGITS:
            print(f"Číslo je příliš krátké ({len(number)} číslic, minimum {MIN_DIGITS}) — končím.")
            return

        make_call(number, leds)

    except KeyboardInterrupt:
        print("\nPřerušeno.")
    finally:
        leds.all_off()
        leds.cleanup()


if __name__ == "__main__":
    main()
