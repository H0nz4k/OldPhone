#!/usr/bin/env python3
"""
Hardwarový test — LED, tlačítka, ciferník.

Spuštění:
  python3 test_hw.py          # kompletní průvodce
  python3 test_hw.py led      # jen LED
  python3 test_hw.py buttons  # jen tlačítka
  python3 test_hw.py dial     # jen ciferník
"""

import sys
import time
import threading

from led import LEDs
from buttons import Buttons
from cifernik import Cifernik

# ── Barvy pro terminál ───────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def header(text):
    print(f"\n{BOLD}{'─'*50}{RESET}")
    print(f"{BOLD}  {text}{RESET}")
    print(f"{BOLD}{'─'*50}{RESET}")

def ok(text):
    print(f"  {GREEN}✓{RESET} {text}")

def info(text):
    print(f"  {CYAN}→{RESET} {text}")

def wait(text="Stiskni Enter pro pokračování..."):
    input(f"\n  {YELLOW}[ {text} ]{RESET}")

# ── LED test ─────────────────────────────────────────────────────────────────

def test_led(leds: LEDs):
    header("TEST LED")

    led_info = [
        (leds.led1, "LED1", "ČERVENÁ",  RED),
        (leds.led2, "LED2", "ZELENÁ",   GREEN),
        (leds.led3, "LED3", "ŽLUTÁ",    YELLOW),
        (leds.led4, "LED4", "MODRÁ",    BLUE),
        (leds.led5, "LED5", "ŽLUTÁ",   YELLOW),
    ]

    # 1. Každá zvlášť — trvale ON
    info("Každá LED se rozsvítí na 1 s...")
    for led, name, color_name, color in led_info:
        print(f"  {color}● {name} ({color_name}){RESET}", end="\r", flush=True)
        led.on()
        time.sleep(1)
        led.off()
        time.sleep(0.2)
        ok(f"{name} ({color_name}) — OK")

    # 2. Vzory blikání
    info("\nBlikací vzory na LED1 (červená):")
    for pattern, label in [("ring", "RING — rychlé"), ("dial", "DIAL — střední"), ("call_active", "HOVOR — pomalé")]:
        print(f"  {RED}  {label}{RESET} (2 s)")
        leds.led1.blink(pattern)
        time.sleep(2)
        leds.led1.off()
        time.sleep(0.3)

    # 3. SMS záblesk
    info("SMS záblesk — 3× všechny LED najednou")
    leds.all_flash(3)
    time.sleep(2)

    # 4. Všechny ON najednou
    info("Všechny ON najednou (2 s)...")
    leds.all_on()
    time.sleep(2)
    leds.all_off()

    ok("LED test dokončen.\n")

# ── Tlačítka test ────────────────────────────────────────────────────────────

def test_buttons(leds: LEDs):
    header("TEST TLAČÍTEK")

    results = {"hook": 0, "btn2": 0}
    lock = threading.Lock()

    def on_hook():
        with lock:
            results["hook"] += 1
        leds.led1.flash(1, 0.05, 0)
        print(f"\n  {GREEN}✓ BTN1 HOOK stisknuto! (celkem: {results['hook']}x){RESET}")

    def on_btn2():
        with lock:
            results["btn2"] += 1
        leds.led2.flash(1, 0.05, 0)
        print(f"\n  {GREEN}✓ BTN2 rezerva stisknuto! (celkem: {results['btn2']}x){RESET}")

    b = Buttons()
    b.on_hook_press    = on_hook
    b.on_button2_press = on_btn2

    info("Mačkej tlačítka. Stiskni Ctrl+C nebo Enter pro ukončení testu.")
    info("  BTN1 HOOK  = pin 36 (BCM 16)  → blikne červená")
    info("  BTN2 rezrv = pin 35 (BCM 19)  → blikne zelená")

    try:
        input()
    except KeyboardInterrupt:
        pass
    finally:
        b.cleanup()

    ok(f"BTN1 HOOK:  {results['hook']}x stisknuto")
    ok(f"BTN2 rezerv: {results['btn2']}x stisknuto\n")

# ── Ciferník test ─────────────────────────────────────────────────────────────

def test_dial(leds: LEDs):
    header("TEST CIFERNÍKU")
    info("PULSE = pin 37 (BCM 26)  |  START = pin 38 (BCM 20)")
    info("Otoč číselníkem (10 číslic nebo Ctrl+C pro konec).\n")

    c = Cifernik()
    digits = []

    try:
        while len(digits) < 10:
            print(f"  Čekám na otočení... ({len(digits)}/10)", end="\r", flush=True)
            d = c.read_digit(timeout=15)
            if d is None:
                print("\n  (timeout — žádné otočení)")
                break
            digits.append(str(d))
            leds.led1.flash(1, 0.08, 0)
            print(f"  {GREEN}✓ Číslo: {d}{RESET}   Dosud: {''.join(digits)}")
    except KeyboardInterrupt:
        print()
    finally:
        c.cleanup()

    if digits:
        ok(f"Vytočeno: {''.join(digits)}\n")
    else:
        info("Žádné číslo nebylo přečteno.\n")

# ── Hlavní ───────────────────────────────────────────────────────────────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    print(f"\n{BOLD}OldPhone — Hardwarový test{RESET}")
    print("Piny: LED1=p40 LED2=p31 LED3=p29 LED4=p32 LED5=p33")
    print("      BTN1=p36 BTN2=p35 | PULSE=p37 START=p38 | GND=p34\n")

    leds = LEDs()

    try:
        if mode in ("all", "led"):
            test_led(leds)
            if mode == "all":
                wait()

        if mode in ("all", "buttons"):
            test_buttons(leds)
            if mode == "all":
                wait()

        if mode in ("all", "dial"):
            test_dial(leds)

    except KeyboardInterrupt:
        print("\n\nPřerušeno.")
    finally:
        leds.all_off()
        leds.cleanup()
        print("Test ukončen.")


if __name__ == "__main__":
    main()
