#!/usr/bin/env python3
"""
LED indikátory — 5 nezávislých LED diod.

Zapojení (každá LED přes rezistor ~220 Ω na GND):
  BCM 21  (pin 40) → LED1  — hlavní (hovory)
  BCM  6  (pin 31) → LED2  — rezerva
  BCM  5  (pin 29) → LED3  — rezerva
  BCM 12  (pin 32) → LED4  — modrá
  BCM 13  (pin 33) → LED5  — žlutá
  GND     (pin 34) → společná katoda všech LED

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
PIN_LED2 =  6   # pin 31 — rezerva
PIN_LED3 =  5   # pin 29 — rezerva
PIN_LED4 = 12   # pin 32 — rezerva
PIN_LED5 = 13   # pin 33 — rezerva

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
    Skupina všech 5 LED — přístup přes leds.led1 … leds.led5.

    Použití:
      leds = LEDs()
      leds.led1.blink("ring")
      leds.led2.on()
      leds.all_off()
      leds.cleanup()
    """

    def __init__(self,
                 pin1: int = PIN_LED1,
                 pin2: int = PIN_LED2,
                 pin3: int = PIN_LED3,
                 pin4: int = PIN_LED4,
                 pin5: int = PIN_LED5):
        self.led1 = LED(pin1)   # BCM 21, pin 40 — hlavní
        self.led2 = LED(pin2)   # BCM  6, pin 31 — rezerva
        self.led3 = LED(pin3)   # BCM  5, pin 29 — rezerva
        self.led4 = LED(pin4)   # BCM 12, pin 32 — modrá
        self.led5 = LED(pin5)   # BCM 13, pin 33 — žlutá
        self._all = [self.led1, self.led2, self.led3, self.led4, self.led5]

    def all_off(self):
        for led in self._all:
            led.off()

    def all_on(self):
        for led in self._all:
            led.on()

    def all_flash(self, count: int = 3):
        for led in self._all:
            led.flash(count)

    def cleanup(self):
        for led in self._all:
            led.cleanup()


# ── Samostatný test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print(f"LED test — LED1=BCM{PIN_LED1}(p40) | LED2=BCM{PIN_LED2}(p31) | LED3=BCM{PIN_LED3}(p29) | LED4=BCM{PIN_LED4}(p32) | LED5=BCM{PIN_LED5}(p33)")

    leds = LEDs()

    mode = sys.argv[1] if len(sys.argv) > 1 else "ring"
    target = sys.argv[2] if len(sys.argv) > 2 else "1"   # 1 / 2 / 3 / all

    led_map = {"1": leds.led1, "2": leds.led2, "3": leds.led3, "4": leds.led4, "5": leds.led5}
    selected = led_map.get(target, leds.led1) if target != "all" else None

    try:
        if mode == "sms":
            print(f"SMS záblesk (3×) — LED{target}")
            if selected:
                selected.sms_flash()
            else:
                leds.all_flash(3)
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
                for l in leds._all:
                    l.blink(mode)
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
