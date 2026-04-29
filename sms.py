#!/usr/bin/env python3
"""
Odešle SMS na číslo a s textem definovaným v config.yaml.
Použití: python3 sms.py
         python3 sms.py 777123456 "Vlastní text zprávy"
"""

import sys
from gsm import GSM, load_config


def main():
    cfg = load_config()
    number = sys.argv[1] if len(sys.argv) > 1 else cfg["sms"]["number"]
    text = sys.argv[2] if len(sys.argv) > 2 else cfg["sms"]["reject_message"]

    print(f"Odesílám SMS na: {number}")
    print(f"Text: {text}")

    gsm = GSM()
    resp = gsm.send_sms(number, text)
    print(f"Odpověď modulu: {resp.strip()}")

    if "+CMGS" in resp:
        print("SMS odeslána úspěšně.")
    else:
        print("Chyba při odesílání SMS.")

    gsm.close()


if __name__ == "__main__":
    main()
