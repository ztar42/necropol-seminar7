"""
Контроль качества этапа 3: сравнение с ручной разметкой (золотой стандарт).

data/gold_dates.csv — 60 случайных статей (random.seed(42)), даты в них
определены вручную по исходному тексту. «?» — значение нельзя установить
однозначно, такие поля в подсчёт не входят.

data/holdout_dates.csv — 40 других случайных статей (random.seed(2026)),
размеченных ПОСЛЕ последней правки кода: честная итоговая оценка.

Запуск:  python3 code/evaluate.py [output/dates_haiku.csv] [data/holdout_dates.csv]
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "gold_dates.csv"


def main(pred_path, gold_path=GOLD):
    # Статьи сопоставляются по началу текста (45 символов), а не по номеру:
    # номера сдвигаются, когда меняется разбиение на статьи (этап 1).
    entries = {r["id"]: r["text"][:45] for r in
               csv.DictReader((ROOT / "output" / "entries.csv").open(encoding="utf-8-sig"))}
    pred = {entries[r["id"]]: r for r in csv.DictReader(open(pred_path, encoding="utf-8-sig"))}
    gold = list(csv.DictReader(open(gold_path, encoding="utf-8-sig")))

    for field in ("birth", "death"):
        tp = fp = fn = 0
        errors = []
        for g in gold:
            truth = g[field]
            if truth == "?":
                continue
            got = pred.get(g["start"], {}).get(field, "")
            if not got and not truth:
                continue             # верно: даты нет, и программа ничего не нашла
            if got == truth:
                tp += 1
            else:
                if got:
                    fp += 1          # нашли, но не то (или там, где ничего нет)
                if truth:
                    fn += 1          # должны были найти, но не нашли верное
                errors.append((g["start"][:25], truth or "—", got or "—", g["comment"]))
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        print(f"{field}: верно {tp}, лишних/неверных {fp}, пропущено {fn} | "
              f"точность {precision:.0%}, полнота {recall:.0%}")
        for e in errors:
            print(f"   [{e[0]}…]: эталон {e[1]}, программа {e[2]}  ({e[3]})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "output" / "dates_haiku.csv",
         sys.argv[2] if len(sys.argv) > 2 else GOLD)
