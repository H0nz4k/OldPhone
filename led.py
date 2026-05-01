#!/usr/bin/env python3
"""
LED indikátor — signalizace hovorů a SMS.

Zapojení:
  BCM 21 (pin 40) → anoda LED (přes rezistor ~220 Ω) → katoda → GND (pin 39)

Vzory blikání:
  RING        — rychlé blikání 0.2 s (příchozí hovor)
  CALL_ACTIVE — pomalé blikání 1 s   (aktivní hovor / vytáčení)
  SMS         — 3× záblesk 0.1 s     (přišla SMS)
  OFF         — zhasnuto
  ON          — trvale rozsvíceno
"""

import threading
import time

try:
    import RPi.GPIO as GPIO
    _GPIO_OK = True
except ImportError:
    _GPIO_OK = False

LED_PIN = 21  # BCM 21, fyzický pin 40


class LED:
    """Neblokující LED indikátor řízený pozadím vláknem."""

    PATTERNS = {
        "off":         None,           # zhasnuto
        "on":          None,           # trvale
        "ring":        (0.15, 0.15),   # příchozí hovor — rychlé
        "call_active": (1.0,  1.0),    # aktivní hovor — pomalé
        "dial":        (0.4,  0.4),    # vytáčení — střední
    }

    def __init__(self, pin=LED_PIN):
        self._pin = pin
        self._thread = None
        self._stop_event = threading.Event()
        self._mode = "off"
        self._lock = threading.Lock()

        if _GPIO_OK:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

    # ── Veřejné metody ───────────────────────────────────────────────────────

    def off(self):
        """Zhasne LED a zastaví blikání."""
        self._set_mode("off")
        self._gpio_out(False)

    def on(self):
        """Trvale rozsvítí LED."""
        self._set_mode("on")
        self._gpio_out(True)

    def blink(self, pattern: str):
        """
        Spustí blikací vzor v pozadí.
        pattern: 'ring' | 'call_active' | 'dial'
        """
        if pattern not in self.PATTERNS or self.PATTERNS[pattern] is None:
            return
        with self._lock:
            if self._mode == pattern:
                return          # již bliká — nic neměníme
            self._mode = pattern
            self._stop_event.set()       # zastavíme starý thread

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._blink_loop,
                                        args=(pattern,), daemon=True)
        self._thread.start()

    def sms_flash(self):
        """3× záblesk — přišla SMS (neblokující, spustí se v pozadí)."""
        threading.Thread(target=self._flash_sequence,
                         args=(3, 0.1, 0.1), daemon=True).start()

    def cleanup(self):
        """Uvolní GPIO."""
        self.off()
        if _GPIO_OK:
            GPIO.cleanup(self._pin)

    # ── Interní ─────────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        with self._lock:
            self._mode = mode
            self._stop_event.set()
        time.sleep(0.05)        # dáme blink threadu čas skončit
        self._stop_event.clear()

    def _gpio_out(self, state: bool):
        if _GPIO_OK:
            GPIO.output(self._pin, GPIO.HIGH if state else GPIO.LOW)

    def _blink_loop(self, pattern: str):
        on_t, off_t = self.PATTERNS[pattern]
        while not self._stop_event.is_set():
            self._gpio_out(True)
            if self._stop_event.wait(on_t):
                break
            self._gpio_out(False)
            self._stop_event.wait(off_t)
        self._gpio_out(False)

    def _flash_sequence(self, count: int, on_t: float, off_t: float):
        for _ in range(count):
            self._gpio_out(True)
            time.sleep(on_t)
            self._gpio_out(False)
            time.sleep(off_t)


# ── Samostatný test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    led = LED()
    mode = sys.argv[1] if len(sys.argv) > 1 else "ring"

    if mode == "sms":
        print("SMS záblesk (3×)")
        led.sms_flash()
        time.sleep(2)
    elif mode in LED.PATTERNS and LED.PATTERNS[mode] is not None:
        print(f"Blikám vzor '{mode}' — Ctrl+C pro ukončení")
        led.blink(mode)
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    else:
        print("Dostupné módy: ring, call_active, dial, sms")

    led.cleanup()
    print("Hotovo.")
