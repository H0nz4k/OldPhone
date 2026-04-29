# OldPhone RPi

Starý telefon s Raspberry Pi a Waveshare GSM/GPRS/GNSS HAT (SIM868) uvnitř.
Projekt umožňuje volat, přijímat hovory a posílat SMS přes 2G síť (T-Mobile CZ).

## Hardware

- Raspberry Pi (3B/4B)
- [Waveshare GSM/GPRS/GNSS HAT](https://www.waveshare.com/wiki/GSM/GPRS/GNSS_HAT) (SIM868)
- SIM karta s podporou 2G (T-Mobile CZ)
- Rotační číselník (ciferník) — integrace připravena

## Zapojení

- HAT nasazen přímo na GPIO piny RPi
- Jumpery na HAT v poloze **B** (GPIO UART → `/dev/ttyS0`)
- GSM anténa připojena

## Instalace

```bash
sudo apt update
sudo apt install python3-pip git minicom -y
pip3 install pyserial pyyaml --break-system-packages
```

Naklonovat repozitář:
```bash
git clone https://github.com/H0nz4k/OldPhone.git
cd OldPhone
```

## Konfigurace

Upravit `config.yaml`:

```yaml
gsm:
  port: /dev/ttyS0
  baud: 9600
  timeout: 1

call:
  number: "731164187"

sms:
  number: "731164187"
  reject_message: "Omlouvám se, nemohu právě teď mluvit. Zavolám zpět."
```

## Použití

### Zavolat na číslo z configu
```bash
python3 call.py
```

### Zavolat na konkrétní číslo
```bash
python3 call.py 777123456
```

### Odeslat SMS z configu
```bash
python3 sms.py
```

### Odeslat SMS na konkrétní číslo s vlastním textem
```bash
python3 sms.py 777123456 "Ahoj, jsem to já!"
```

### Naslouchat příchozím hovorům
```bash
python3 incoming.py
```

Při příchozím hovoru se zobrazí číslo volajícího a nabídka:
- `1` — Přijmout hovor
- `2` — Odmítnout hovor
- `3` — Odmítnout a odeslat SMS (text z configu)

## Struktura projektu

```
OldPhone/
├── config.yaml      # konfigurace (čísla, texty, serial port)
├── gsm.py           # GSM třída — komunikace s modulem
├── call.py          # vytočení hovoru
├── sms.py           # odeslání SMS
├── incoming.py      # příchozí hovory
├── postup.md        # dokumentace postupu vývoje
└── README.md
```

## Plán dalšího rozvoje

- [ ] Integrace rotačního číselníku (ciferníku) přes GPIO
- [ ] Detekce zvednutí/zavěšení sluchátka přes GPIO
- [ ] Automatické spuštění při startu RPi (systemd service)
- [ ] Zvukový výstup přes sluchátko telefonu
