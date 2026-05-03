from machine import Pin
import time

pulse_pin = Pin(28, Pin.IN, Pin.PULL_UP)
start_pin = Pin(27, Pin.IN, Pin.PULL_UP)

pulse_count = 0
last_state = 1
last_change_time = 0

while True:

    # čekej na začátek (START=LOW = točí se)
    if start_pin.value() == 0:
        pulse_count = 0
        last_state = pulse_pin.value()
        last_change_time = time.ticks_ms()
        print("--- Start otaceni ---")

        # dokud točíš
        while start_pin.value() == 0:
            now = time.ticks_ms()
            state = pulse_pin.value()

            # detekce změny (edge)
            if state != last_state:
                dt = time.ticks_diff(now, last_change_time)
                if dt > 20:
                    last_change_time = now

                    # počítáme jen FALLING edge
                    if state == 0:
                        pulse_count += 1
                        print(f"  PULSE falling  dt={dt}ms  pocet={pulse_count}")
                    else:
                        print(f"  PULSE rising   dt={dt}ms")
                else:
                    edge = "falling" if state == 0 else "rising"
                    print(f"  SKIP {edge}  dt={dt}ms  (bounce)")

                last_state = state

            time.sleep(0.001)

        # konec čísla
        number = pulse_count
        if number == 10:
            number = 0

        print(f">>> Cislo: {number}  (pulzu: {pulse_count})")

        time.sleep(0.2)

    time.sleep(0.01)
