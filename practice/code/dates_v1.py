"""
Этап 3, версия 1 (ответ на промт 1): даты рождения и смерти.
Наивный вариант: «правильные» названия месяцев и знак смерти «†» / «+».
Оставлен в проекте для сравнения с версией 2.
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "output" / "entries.csv"
OUT = ROOT / "output" / "dates_v1.csv"

MONTHS = ["января", "февраля", "марта", "апрѣля", "мая", "іюня",
          "іюля", "августа", "сентября", "октября", "ноября", "декабря"]
MONTH_RE = "|".join(MONTHS)
DATE = rf"(\d{{1,2}})\s+({MONTH_RE})\s+(\d{{4}})"

BIRTH = re.compile(rf"р\.\s*{DATE}")
DEATH = re.compile(rf"[†+]\s*{DATE}")


def main():
    rows = list(csv.DictReader(IN.open(encoding="utf-8-sig")))
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "birth", "death"])
        for r in rows:
            b = BIRTH.search(r["text"])
            d = DEATH.search(r["text"])
            fmt = lambda m: (f"{m.group(3)}-{MONTHS.index(m.group(2)) + 1:02d}-"
                             f"{int(m.group(1)):02d}") if m else ""
            w.writerow([r["id"], fmt(b), fmt(d)])


if __name__ == "__main__":
    main()
