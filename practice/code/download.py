"""
Этап 0. Скачивание источника: OCR-текст «Петербургского некрополя», т. 1,
из Internet Archive (https://archive.org/details/peterburgskijnekropolt1ag60).

Выход: data/necropol_t1.txt
Если файл уже есть, повторно не скачивает (чтобы скачать заново: --force).
"""
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "necropol_t1.txt"
URL = ("https://archive.org/download/peterburgskijnekropolt1ag60/"
       "peterburgskijnekropolt1ag60_djvu.txt")
ATTEMPTS = 4

MANUAL = f"""
Не удалось скачать автоматически (archive.org иногда временно отвечает ошибкой).
Подождите пару минут и запустите скрипт снова — или скачайте файл вручную:
  1) откройте в браузере {URL}
  2) сохраните страницу (Файл -> Сохранить как…) в папку data под именем necropol_t1.txt
"""


def fetch():
    """Скачивает файл; при временной ошибке сервера пробует ещё раз с паузой."""
    request = urllib.request.Request(URL, headers={"User-Agent": "necropol-seminar/1.0"})
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  попытка {attempt}/{ATTEMPTS} не удалась: {e}")
            if attempt < ATTEMPTS:
                time.sleep(5 * attempt)
    sys.exit(MANUAL)


def main():
    if DEST.exists() and "--force" not in sys.argv:
        print(f"Файл уже есть: {DEST} ({DEST.stat().st_size:,} байт). "
              f"Чтобы скачать заново: python3 code/download.py --force")
        return
    print(f"Скачиваю {URL} …")
    data = fetch()
    text = data.decode("utf-8")
    # Контроль: это действительно нужный текст, а не страница ошибки.
    if "Абаза, Аггей" not in text:
        sys.exit("Ошибка: в скачанном файле нет начала словаря («Абаза, Аггей»).")
    DEST.parent.mkdir(exist_ok=True)
    DEST.write_text(text, encoding="utf-8")
    print(f"Готово: {DEST} — {len(data):,} байт, {text.count(chr(10)):,} строк.")


if __name__ == "__main__":
    main()
