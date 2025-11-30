import os
import time
import re
import json

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ============================================================
#   LISTA PILOTI (UNICA)
#   Qui cambi i nomi PSN quando serve
# ============================================================

PILOTI = [
    "RKE_MaxEpico1979",
    "RKE_Ekin",
    "RKE__Giuls",
    "RKE_Bazzo",
    "RKE_Cjcerbola",
    "RKE_Pepyx29",
    "RKE_MWalter",
    "MontyRidesAgain",
    "Daviderom_91",
    "RKE_BALDO44",
    "JigenBiker",
    "brummybulldog",
]

# Ordine fisso in classifica (stesso della lista)
ALL_PILOTI = PILOTI[:]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AVATAR_DIR = os.path.join(BASE_DIR, "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

CSS_SELECTOR_AVATAR = "img.driver-photo"


# ====================== FUNZIONI ============================

def estrai_numero(text: str) -> int:
    """Prende il primo intero da una stringa, accetta . e , come separatori."""
    if not text:
        return 0
    clean = text.replace(",", "").replace(".", "")
    m = re.search(r"(\d+)", clean)
    if not m:
        return 0
    return int(m.group(1))


def get_stat_value_from_spans(driver, label_text: str) -> str:
    """
    Cerca span.stat-label che contiene label_text
    e prende il fratello span.stat-value.
    """
    labels = driver.find_elements(By.CSS_SELECTOR, "span.stat-label")
    for lab in labels:
        try:
            if label_text.lower() in lab.text.lower():
                value_span = lab.find_element(
                    By.XPATH,
                    "following-sibling::span[contains(@class,'stat-value')]",
                )
                return value_span.text.strip()
        except Exception:
            continue
    return ""


def fallback_from_text(result_text: str):
    """
    Fallback su testo grezzo di #result con regex permissive.
    Torna (dr, wins, races).
    """
    dr = 0
    wins = 0
    races = 0

    m = re.search(
        r"DR\s*Points?[:：]?\s*([0-9\.,]+)",
        result_text,
        re.IGNORECASE,
    )
    if m:
        dr = estrai_numero(m.group(1))

    m = re.search(
        r"Wins?[:：]?\s*([0-9\.,]+)",
        result_text,
        re.IGNORECASE,
    )
    if m:
        wins = estrai_numero(m.group(1))

    m = re.search(
        r"Races?[:：]?\s*([0-9\.,]+)",
        result_text,
        re.IGNORECASE,
    )
    if m:
        races = estrai_numero(m.group(1))

    return dr, wins, races


def get_values_with_fallback(driver, psn: str):
    """
    Torna (dr_value, wins, races, result_text) con:
    - primo passaggio via span.stat-label/value
    - secondo passaggio via regex su testo, che può correggere i valori
    """
    result_el = driver.find_element(By.ID, "result")
    result_text = result_el.text

    dr_text = get_stat_value_from_spans(driver, "DR Points")
    wins_text = get_stat_value_from_spans(driver, "Wins")
    races_text = get_stat_value_from_spans(driver, "Races")

    dr_value = estrai_numero(dr_text)
    wins = estrai_numero(wins_text)
    races = estrai_numero(races_text)

    print(f"  [{psn}] span -> DR='{dr_text}' Wins='{wins_text}' Races='{races_text}'")
    print(f"  [{psn}] span numeri -> DR={dr_value}, Wins={wins}, Races={races}")

    fb_dr, fb_wins, fb_races = fallback_from_text(result_text)
    print(f"  [{psn}] fallback regex -> DR={fb_dr}, Wins={fb_wins}, Races={fb_races}")

    if fb_dr > 0:
        dr_value = fb_dr
    if fb_wins > 0:
        wins = fb_wins
    if fb_races > 0:
        races = fb_races

    print(f"  [{psn}] final -> DR={dr_value}, Wins={wins}, Races={races}")

    return dr_value, wins, races, result_text


# ========================== MAIN ============================

def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    new_results = {}

    print("=== AGGIORNAMENTO DR PILOTI (HTML + fallback regex) ===\n")

    for psn in PILOTI:
        print("=================================")
        print(f"Lettura dati per: {psn}")
        skip_update = False

        try:
            driver.get("https://gtsh-rank.com/profile/")

            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "psnid"))
            )

            input_field = driver.find_element(By.ID, "psnid")
            input_field.clear()
            input_field.send_keys(psn)

            get_button = driver.find_element(By.XPATH, '//button[text()="GET"]')
            get_button.click()

            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "result"))
            )

            result_el = driver.find_element(By.ID, "result")
            result_text_raw = result_el.text

            if "API not available" in result_text_raw:
                print("  API not available, NON aggiorno questo pilota, tengo i dati vecchi.")
                skip_update = True
            else:
                time.sleep(2)

                dr_value, wins, races, result_text = get_values_with_fallback(driver, psn)

                print(f"  [{psn}] TESTO COMPLETO RESULT:")
                print("  ---------------------------------")
                print(result_text)
                print("  ---------------------------------")

                if dr_value == 0 and wins == 0 and races == 0:
                    print("  Tutti i valori 0, probabilmente lettura fallita, NON aggiorno questo pilota.")
                    skip_update = True
                else:
                    winrate = f"{(wins / races * 100):.1f}%" if races > 0 else "-"

            # avatar, anche se saltiamo i numeri può comunque aggiornarsi
            try:
                avatar_el = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, CSS_SELECTOR_AVATAR))
                )
                avatar_target = os.path.join(AVATAR_DIR, f"{psn}.png")
                avatar_el.screenshot(avatar_target)
                print("  Avatar salvato.")
            except Exception as e_avatar:
                print(f"  Impossibile salvare avatar per {psn}: {e_avatar}")

            if not skip_update:
                new_results[psn] = {
                    "psn": psn,
                    "dr": dr_value,
                    "delta": dr_value,
                    "wins": wins,
                    "races": races,
                    "winrate": winrate,
                }
                print(f"  RISULTATO FINALE {psn}: DR={dr_value}, Wins={wins}, Races={races}, Win%={winrate}")
            else:
                print(f"  Nessun update per {psn}, in merge terrò i valori precedenti.")

        except Exception as e:
            print(f"  Errore per {psn}: {e}")
            print("  Nessun update, terrò i valori vecchi in merge.")

        print("  Pausa 3 secondi...\n")
        time.sleep(3)

    driver.quit()

    # ===== MERGE CON VECCHIO dr.json =====
    old_by_psn = {}

    if os.path.exists("dr.json"):
        try:
            with open("dr.json", "r", encoding="utf-8") as f:
                old_list = json.load(f)
                old_by_psn = {item["psn"]: item for item in old_list if "psn" in item}
        except Exception as e:
            print(f"Errore lettura dr.json esistente: {e}")

    final_results = []

    for psn in ALL_PILOTI:
        if psn in new_results:
            final_results.append(new_results[psn])
        elif psn in old_by_psn:
            final_results.append(old_by_psn[psn])
        else:
            final_results.append({
                "psn": psn,
                "dr": 0,
                "delta": 0,
                "wins": 0,
                "races": 0,
                "winrate": "-",
            })

    with open("dr.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, indent=2, ensure_ascii=False)

    print("\nCreato dr.json con tutti i piloti (nuovi + vecchi).")


if __name__ == "__main__":
    main()
