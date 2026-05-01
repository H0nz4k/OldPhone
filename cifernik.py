#!/usr/bin/env python3
"""
Čtení rotačního ciferníku (číselníku) na Raspberry Pi.

Zapojení:
  BCM 26  (pin 37) → PULSE  — drát pulzů ciferníku
  BCM 20  (pin 38) → START  — drát "číselník se točí" (LOW = točí se)
  GND     (pin 39) → GND    — společná zem

Logika:
  - START jde do LOW → počítáme falling edges na PULSE
  - START jde zpět do HIGH → konec otáčení
  - 10 pulzů = číslice 0, jinak počet = číslice

Vyžaduje pigpio daemon (přesné DMA-based GPIO, <1µs přesnost):
  sudo apt install pigpio python3-pigpio
  sudo systemctl enable pigpiod && sudo systemctl start pigpiod

Použití:
  python3 cifernik.py            # testovací smyčka — vypisuje čísla
  from cifernik import Cifernik  # jako modul v jiných skriptech
"""

import time
import threading

try:
    import pigpio
    _pi = pigpio.pi()
    PIGPIO_OK = _pi.connected
    if not PIGPIO_OK:
        print("[WARN] pigpiod neběží — spusť: sudo systemctl start pigpiod")
except ImportError:
    PIGPIO_OK = False
    _pi = None
    print("[WARN] pigpio není nainstalováno: sudo apt install python3-pigpio")

# ── Konfigurace pinů (BCM čísla) ────────────────────────────────────────────
PIN_PULSE = 26   # pin 37
PIN_START = 20   # pin 38


class Cifernik:
    """
    Třída pro čtení rotačního ciferníku pomocí pigpio (DMA přesnost).
    """

    def __init__(self, pin_pulse=PIN_PULSE, pin_start=PIN_START):
        self.pin_pulse = pin_pulse
        self.pin_start = pin_start
        if PIGPIO_OK:
            _pi.set_mode(pin_pulse, pigpio.INPUT)
            _pi.set_mode(pin_start, pigpio.INPUT)
            _pi.set_pull_up_down(pin_pulse, pigpio.PUD_UP)
            _pi.set_pull_up_down(pin_start, pigpio.PUD_UP)

    def read_digit(self, timeout=10.0):
        """
        Čeká na otočení ciferníku a vrátí číslo (0–9).
        Vrátí None pokud timeout vyprší nebo pigpio není dostupné.
        """
        if not PIGPIO_OK:
            return None

        deadline = time.time() + timeout

        # Čekáme na START (pin jde do LOW)
        while _pi.read(self.pin_start) == 1:
            if time.time() > deadline:
                return None
            time.sleep(0.005)

        # Počítáme pulzy pomocí pigpio callback (DMA přesnost, žádné preempce)
        pulse_count = 0
        lock = threading.Lock()
        last_fall = [0.0]
        DEBOUNCE = 0.020   # 20 ms — zákmity jsou <5ms, pulzy ~100ms od sebe
        done = [False]

        def _on_pulse(gpio, level, tick):
            nonlocal pulse_count
            if done[0]:
                return          # START už šel HIGH → ignoruj pozdní bounce
            now = time.time()
            with lock:
                if now - last_fall[0] >= DEBOUNCE:
                    pulse_count += 1
                    last_fall[0] = now

        cb = _pi.callback(self.pin_pulse, pigpio.FALLING_EDGE, _on_pulse)

        # Čekáme dokud se číselník točí
        while _pi.read(self.pin_start) == 0:
            time.sleep(0.002)

        # Označíme konec — callback přestane počítat
        done[0] = True
        # Krátká pauza jen pro případ že poslední callback ještě letí
        time.sleep(0.015)
        cb.cancel()

        time.sleep(0.020)

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
        pass   # pigpio nevyžaduje cleanup pinů


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
