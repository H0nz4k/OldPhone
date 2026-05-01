#!/usr/bin/env python3
"""
Čtení rotačního ciferníku (číselníku) na Raspberry Pi.

Zapojení:
  BCM 26  (pin 37) → PULSE  — drát pulzů ciferníku
  BCM 20  (pin 38) → START  — drát "číselník se točí" (LOW = točí se)
  GND     (pin 39) → GND    — společná zem

Logika (stejná jako na Pico):
  - START jde do LOW → začínáme počítat pulzy na PULSE (falling edge)
  - START jde zpět do HIGH → konec otáčení, vyhodnotíme počet pulzů
  - 10 pulzů = číslice 0, jinak počet = číslice

Použití:
  python3 cifernik.py            # testovací smyčka — vypisuje čísla
  from cifernik import Cifernik  # jako modul v jiných skriptech
"""

import time

try:
    import RPi.GPIO as GPIO
    GPIO_OK = True
except ImportError:
    GPIO_OK = False
    print("[WARN] RPi.GPIO není dostupné — spuštěn v simulačním módu (bez hardwaru)")

# ── Konfigurace pinů (BCM čísla) ────────────────────────────────────────────
PIN_PULSE = 26   # pin 37
PIN_START = 20   # pin 38


class Cifernik:
    """
    Třída pro čtení rotačního ciferníku.
    Používá RPi.GPIO polling (stejná logika jako Pico verze).
    """

    def __init__(self, pin_pulse=PIN_PULSE, pin_start=PIN_START):
        self.pin_pulse = pin_pulse
        self.pin_start = pin_start
        if GPIO_OK:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin_start, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(pin_pulse, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def read_digit(self, timeout=10.0):
        """
        Čeká na otočení ciferníku a vrátí číslo (0–9).
        Vrátí None pokud timeout vyprší nebo GPIO není dostupné.
        """
        if not GPIO_OK:
            return None

        deadline = time.time() + timeout

        # Čekáme na START (pin jde do LOW)
        while GPIO.input(self.pin_start) == 1:
            if time.time() > deadline:
                return None
            time.sleep(0.005)

        # Krátká pauza — necháme kontakty ustálit po START
        time.sleep(0.020)

        # Počítáme pulzy: detekujeme falling + rising edge a měříme délku LOW.
        # Pravý pulz: LOW ~30-50 ms | Zákmit: LOW < 10 ms → ignoruj
        MIN_PULSE_S = 0.010   # 10 ms minimum

        pulse_count = 0
        last_state = GPIO.input(self.pin_pulse)
        fall_time = None

        while GPIO.input(self.pin_start) == 0:
            state = GPIO.input(self.pin_pulse)

            if last_state == 1 and state == 0:
                # Falling edge — zaznamenáme čas
                fall_time = time.time()

            elif last_state == 0 and state == 1:
                # Rising edge — změříme délku pulzu
                if fall_time is not None:
                    duration = time.time() - fall_time
                    if duration >= MIN_PULSE_S:
                        pulse_count += 1
                    # debug — odkomentuj pro ladění:
                    # print(f"    [pulse {duration*1000:.1f} ms → {'OK' if duration >= MIN_PULSE_S else 'skip'}]")
                fall_time = None

            last_state = state
            time.sleep(0.001)

        # ── Zachytit poslední pulz ───────────────────────────────────────────
        # START šel HIGH, ale PULSE může být stále LOW (poslední pulz ještě běží).
        # Počkáme až PULSE dokončí a pulz započítáme.
        if fall_time is not None:
            deadline2 = time.time() + 0.150   # max 150 ms čekání
            while GPIO.input(self.pin_pulse) == 0 and time.time() < deadline2:
                time.sleep(0.001)
            duration = time.time() - fall_time
            if duration >= MIN_PULSE_S:
                pulse_count += 1
            # print(f"    [last pulse {duration*1000:.1f} ms → {'OK' if duration >= MIN_PULSE_S else 'skip'}]")

        # Krátká pauza po ukončení — necháme kontakty ustálit
        time.sleep(0.050)

        # Vyhodnocení: 10 pulzů = 0, jinak hodnota = počet pulzů
        if pulse_count >= 10:
            return 0
        return pulse_count if pulse_count > 0 else None

    def read_number(self, digits=None, timeout_per_digit=8.0, done_timeout=2.5):
        """
        Čte sekvenci číslic dokud:
          - není přečten zadaný počet číslic (digits), nebo
          - uživatel přestane točit (done_timeout sekund ticho)
        Vrátí string s přečteným číslem, např. "0731164187"
        """
        result = []
        while True:
            digit = self.read_digit(timeout=timeout_per_digit)
            if digit is None:
                break
            result.append(str(digit))
            print(f"  [{digit}]  → dosud: {''.join(result)}")
            if digits is not None and len(result) >= digits:
                break
            # Krátká pauza — pokud do done_timeout nic, konec
            digit2 = self.read_digit(timeout=done_timeout)
            if digit2 is None:
                break
            result.append(str(digit2))
            print(f"  [{digit2}]  → dosud: {''.join(result)}")
            if digits is not None and len(result) >= digits:
                break
        return "".join(result)

    def cleanup(self):
        if GPIO_OK:
            GPIO.cleanup([self.pin_pulse, self.pin_start])


# ── Testovací smyčka ─────────────────────────────────────────────────────────

def main():
    print(f"Ciferník — PULSE=BCM{PIN_PULSE} (pin 37), START=BCM{PIN_START} (pin 38)")
    print("Otáčej číselníkem. Ctrl+C pro ukončení.\n")

    c = Cifernik()
    try:
        while True:
            print("Čekám na otočení...")
            digit = c.read_digit(timeout=30)
            if digit is not None:
                print(f">>> Číslo: {digit}\n")
            else:
                print("(timeout — žádné otočení)\n")
    except KeyboardInterrupt:
        print("\nUkončuji.")
    finally:
        c.cleanup()


if __name__ == "__main__":
    main()
