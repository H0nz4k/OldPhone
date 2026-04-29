# OldPhone RPi - Postup

## Stav projektu

- Starý telefon jako schránka
- Uvnitř: Raspberry Pi + Waveshare GSM/GPRS/GNSS HAT (SIM800)
- Číselník (ciferník) už funguje
- Git repo: https://github.com/H0nz4k/OldPhone.git

---

## Krok 1: Prvotní nastavení RPi

Po nahrání Raspianu je potřeba povolit UART a zakázat serial console:

```bash
sudo raspi-config
# -> Interface Options -> Serial Port
# -> Login shell over serial: NO
# -> Serial port hardware: YES
```

Také doporučuji rovnou:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip git minicom -y
pip3 install pyserial --break-system-packages
```

---

## Krok 2: Fyzické zapojení HAT modulu

- HAT se nasazuje přímo na GPIO piny RPi
- Zkontrolovat jumper nastavení na HAT (jsou dva jumpery vedle USB konektoru):
  - poloha **B** = GPIO UART (HAT nasazený přímo na RPi přes piny) → port `/dev/ttyS0` ✅ **toto chceme**
  - poloha **A** = USB rozhraní (HAT připojený USB kabelem k RPi) → jiný port, nutný USB kabel
- Vložit SIM kartu (nejlépe bez PIN, nebo PIN předem vypnout)
- Připojit GSM anténu!

---

## Krok 3: Test AT příkazů

```bash
minicom -D /dev/ttyS0 -b 9600
```

Základní AT příkazy pro ověření funkce:

| Příkaz | Popis |
|---|---|
| `AT` | Test spojení → odpověď `OK` |
| `AT+CSQ` | Síla signálu |
| `AT+CREG?` | Registrace v síti |
| `ATD731XXXXXX;` | Vytočení čísla |
| `ATH` | Zavěšení |
| `ATA` | Přijetí hovoru |

---

## Krok 4: Python třída pro GSM modul

Soubor `gsm.py`:

```python
import serial
import time

class GSM:
    def __init__(self, port='/dev/ttyS0', baud=9600):
        self.ser = serial.Serial(port, baud, timeout=1)
        time.sleep(1)

    def send_at(self, cmd, delay=0.5):
        self.ser.write((cmd + '\r\n').encode())
        time.sleep(delay)
        return self.ser.read(self.ser.in_waiting).decode()

    def test(self):
        return self.send_at('AT')

    def signal(self):
        return self.send_at('AT+CSQ')

    def call(self, number):
        return self.send_at(f'ATD{number};')

    def hangup(self):
        return self.send_at('ATH')

    def answer(self):
        return self.send_at('ATA')
```

---

## Krok 5: Integrace ciferníku + GSM

Logika fungování:
1. Ciferník vytočí číslo → číslo se ukládá do stringu
2. Zvednutí sluchátka → trigger pro zahájení volání
3. Zavěšení sluchátka → `ATH` (zavěšení hovoru)
4. `ATD<číslo>;` → zavolá na vytočené číslo

Příklad hlavní smyčky `main.py`:

```python
from gsm import GSM

gsm = GSM()
dialed_number = ""

def on_digit_dialed(digit):
    global dialed_number
    dialed_number += str(digit)
    print(f"Vytočeno: {dialed_number}")

def on_handset_lifted():
    if dialed_number:
        print(f"Volám: {dialed_number}")
        gsm.call(dialed_number)

def on_handset_hung():
    global dialed_number
    gsm.hangup()
    dialed_number = ""
```

---

## Krok 6: Git nastavení na RPi

```bash
git clone https://github.com/H0nz4k/OldPhone.git
cd OldPhone
git config user.name "H0nz4k"
git config user.email "tvuj@email.cz"
```

---

## TODO

- [ ] Nahrát Raspbian a nakonfigurovat UART
- [ ] Fyzicky zapojit HAT a otestovat AT příkazy
- [ ] Napsat a otestovat Python třídu GSM
- [ ] Propojit ciferník s GSM logikou
- [ ] Otestovat celý hovor (vytočení → zvonění → přijetí → zavěšení)
- [ ] Zapojit mikrofon a reproduktor sluchátka
