#!/usr/bin/env python3
"""
Fyzická tlačítka pro telefon.

Zapojení (interní pull-up — tlačítko zkratuje pin na GND):
  BCM 16  (pin 36) → Tlačítko 1 — HOOK (zvednout/položit sluchátko)
  BCM 19  (pin 35) → Tlačítko 2 — rezerva pro budoucí použití
  GND     (pin 34) → společná zem obou tlačítek

Chování HOOK tlačítka:
  - Zvoní telefon  → stisknutí = přijmout hovor
  - Aktivní hovor  → stisknutí = zavěsit
  - Klid           → stisknutí = ignorováno (nebo callback on_idle_press)
"""

import time
import threading

try:
    import RPi.GPIO as GPIO
    _GPIO_OK = True
except ImportError:
    _GPIO_OK = False

PIN_HOOK    = 16   # pin 36 — sluchátko
PIN_BUTTON2 = 19   # pin 35 — rezerva

DEBOUNCE_MS = 50   # ms — ochrana proti zákmitům


class Buttons:
    """
    Neblokující obsluha tlačítek přes GPIO interrupt.

    Callbacky (nastav po vytvoření objektu):
      on_hook_press()      — zavolá se při stisku HOOK tlačítka
      on_button2_press()   — zavolá se při stisku Tlačítka 2 (rezerva)
    """

    def __init__(self, pin_hook=PIN_HOOK, pin_btn2=PIN_BUTTON2):
        self._pin_hook = pin_hook
        self._pin_btn2 = pin_btn2
        self.on_hook_press    = None   # přiřaď zvenčí
        self.on_button2_press = None   # přiřaď zvenčí

        if _GPIO_OK:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin_hook, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(pin_btn2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin_hook, GPIO.FALLING,
                callback=self._cb_hook,
                bouncetime=DEBOUNCE_MS,
            )
            GPIO.add_event_detect(
                pin_btn2, GPIO.FALLING,
                callback=self._cb_btn2,
                bouncetime=DEBOUNCE_MS,
            )
        else:
            print("[WARN] RPi.GPIO není dostupné — tlačítka neaktivní")

    def _cb_hook(self, channel):
        if self.on_hook_press:
            threading.Thread(target=self.on_hook_press, daemon=True).start()

    def _cb_btn2(self, channel):
        if self.on_button2_press:
            threading.Thread(target=self.on_button2_press, daemon=True).start()

    def cleanup(self):
        if _GPIO_OK:
            GPIO.remove_event_detect(self._pin_hook)
            GPIO.remove_event_detect(self._pin_btn2)
            GPIO.cleanup([self._pin_hook, self._pin_btn2])


# ── Samostatný test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Test tlačítek — HOOK=BCM{PIN_HOOK} (pin 36), BTN2=BCM{PIN_BUTTON2} (pin 35)")
    print("Mačkej tlačítka. Ctrl+C pro ukončení.\n")

    def hook_pressed():
        print("[HOOK] Tlačítko sluchátka stisknuto")

    def btn2_pressed():
        print("[BTN2] Tlačítko 2 stisknuto")

    b = Buttons()
    b.on_hook_press    = hook_pressed
    b.on_button2_press = btn2_pressed

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nUkončuji.")
    finally:
        b.cleanup()
