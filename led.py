#!/usr/bin/env python3
"""
LED indikátory — 3 nezávislé LED diody.

Zapojení (každá LED přes rezistor ~220 Ω na GND):
  BCM 21  (pin 40) → LED1  — hlavní (hovory)
  BCM 13  (pin 33) → LED2  — rezerva
  BCM 12  (pin 32) → LED3  — rezerva
  GND     (pin 39) → společná katoda všech LED

Vzory blikání:
  ring        — rychlé blikání 0.15 s (příchozí hovor)
  call_active — pomalé blikání 1 s   (aktivní hovor)
  dial        — střední blikání 0.4 s (vytáčení)
  on          — trvale rozsvíceno
  off         — zhasnuto

Použití jako modul:
  from led import LED, LEDs
  leds = LEDs()          # všechny 3 najednou
  leds.led1.blink("ring")
  leds.led2.on()
  leds.led3.sms_flash()
  leds.cleanup()

  # nebo samostatně:
  led = LED(pin=21)
"""

import threading
import time

try:
    import RPi.GPIO as GPIO
    _GPIO_OK = True
except ImportError:
    _GPIO_OK = False

# ── Výchozí piny ────────────────────────────────────────────────────────────
PIN_LED1 = 21   # pin 40 — hlavní (hovory)
PIN_LED2 = 13   # pin 33 — rezerva
PIN_LED3 = 12   # pin 32 — rezerva

_gpio_initialized = False


def _ensure_gpio_mode():
    global _gpio_initialized
    if _GPIO_OK and not _gpio_initialized:
        GPIO.setmode(GPIO.BCM)
        _gpio_initialized = True


class LED:
    """Neblokující LED indikátor řízený pozadím vláknem."""

    PATTERNS = {
        "ring":        (0.15, 0.15),
        "call_active": (1.0,  1.0),
        "dial":        (0.4,  0.4),
    }

    def __init__(self, pin: int):
        self._pin = pin
        self._stop_event = threading.Event()
        self._mode = "off"
        self._lock = threading.Lock()

        _ensure_gpio_mode()
        if _GPIO_OK:
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
        if pattern not in self.PATTERNS:
            return
        with self._lock:
            if self._mode == pattern:
                return
            self._mode = pattern
            self._stop_event.set()

        self._stop_event.clear()
        threading.Thread(target=self._blink_loop,
                         args=(pattern,), daemon=True).start()

    def flash(self, count: int = 3, on_t: float = 0.1, off_t: float = 0.1):
        """N× záblesk v pozadí (neblokující)."""
        threading.Thread(target=self._flash_sequence,
                         args=(count, on_t, off_t), daemon=True).start()

    def sms_flash(self):
        """3× krátký záblesk — přišla SMS."""
        self.flash(3, 0.1, 0.1)

    def cleanup(self):
        """Zhasne LED a uvolní GPIO pin."""
        self.off()
        if _GPIO_OK:
            try:
                GPIO.cleanup(self._pin)
            except Exception:
                pass

    # ── Interní ─────────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        with self._lock:
            self._mode = mode
            self._stop_event.set()
        time.sleep(0.05)
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

    def __repr__(self):
        return f"LED(pin=BCM{self._pin}, mode={self._mode!r})"


class LEDs:
    """
    Skupina všech 3 LED — pohodlný přístup přes leds.led1 / .led2 / .led3.

    Použití:
      leds = LEDs()
      leds.led1.blink("ring")
      leds.led2.on()
      leds.cleanup()
    """

    def __init__(self,
                 pin1: int = PIN_LED1,
                 pin2: int = PIN_LED2,
                 pin3: int = PIN_LED3):
        self.led1 = LED(pin1)   # BCM 21, pin 40 — hlavní
        self.led2 = LED(pin2)   # BCM 13, pin 33 — rezerva
        self.led3 = LED(pin3)   # BCM 12, pin 32 — rezerva

    def all_off(self):
        self.led1.off()
        self.led2.off()
        self.led3.off()

    def all_on(self):
        self.led1.on()
        self.led2.on()
        self.led3.on()

    def cleanup(self):
        self.led1.cleanup()
        self.led2.cleanup()
        self.led3.cleanup()


# ── Samostatný test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print(f"LED test — LED1=BCM{PIN_LED1}(pin40) | LED2=BCM{PIN_LED2}(pin33) | LED3=BCM{PIN_LED3}(pin32)")

    leds = LEDs()

    mode = sys.argv[1] if len(sys.argv) > 1 else "ring"
    target = sys.argv[2] if len(sys.argv) > 2 else "1"   # 1 / 2 / 3 / all

    led_map = {"1": leds.led1, "2": leds.led2, "3": leds.led3}
    selected = led_map.get(target, leds.led1) if target != "all" else None

    try:
        if mode == "sms":
            print(f"SMS záblesk (3×) — LED{target}")
            if selected:
                selected.sms_flash()
            else:
                leds.led1.sms_flash(); leds.led2.sms_flash(); leds.led3.sms_flash()
            time.sleep(2)
        elif mode == "on":
            print(f"Trvale ON — LED{target}. Ctrl+C pro ukončení.")
            if selected:
                selected.on()
            else:
                leds.all_on()
            while True:
                time.sleep(0.5)
        elif mode in LED.PATTERNS:
            print(f"Blikám vzor '{mode}' — LED{target}. Ctrl+C pro ukončení.")
            if selected:
                selected.blink(mode)
            else:
                leds.led1.blink(mode); leds.led2.blink(mode); leds.led3.blink(mode)
            while True:
                time.sleep(0.5)
        else:
            print("Použití: python3 led.py <mód> [číslo_led]")
            print("  mód:      ring | call_active | dial | sms | on")
            print("  číslo_led: 1 | 2 | 3 | all  (výchozí: 1)")
    except KeyboardInterrupt:
        pass
    finally:
        leds.cleanup()
        print("Hotovo.")
