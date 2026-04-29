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
    r = resp.strip()
    print(f"Odpověď modulu:\n{r if r else '(prázdná — zkontroluj signál, registraci sítě a formát čísla +420…)'}")

    if "+CMGS" in resp:
        print("SMS odeslána úspěšně.")
    elif "+CMS ERROR" in resp or ("ERROR" in resp and "+CMGS" not in resp):
        print("Modul vrátil chybu (viz odpověď výše).")
    else:
        print("Chyba při odesílání SMS.")

    gsm.close()


if __name__ == "__main__":
    main()
