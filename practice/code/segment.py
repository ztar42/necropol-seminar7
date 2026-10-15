"""
Этап 1. Разбиение OCR-текста «Петербургского некрополя» (т. 1) на статьи.

Вход:  data/necropol_t1.txt  (OCR-текст с archive.org)
Выход: output/entries.csv    (id, surname, text)
       output/segment_report.txt (контроль: сколько статей, что выброшено)
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "necropol_t1.txt"
OUT = ROOT / "output" / "entries.csv"
REPORT = ROOT / "output" / "segment_report.txt"
# Все файлы пишутся в кодировке utf-8-sig: с ней Excel правильно показывает кириллицу.

# Словарная часть начинается со статьи «Абаза, Аггей Васильевич»;
# всё, что выше, — предисловие и список кладбищ.
START_MARKER = "Абаза, Аггей"

# Начало статьи: Фамилия (с дефисами: «Гюне-фонъ», «Анненковъ-Нагель»),
# затем запятая. Разрешаем латинские буквы-двойники, которые путает OCR.
ENTRY_START = re.compile(r"^[А-ЯЁA-Z][а-яёъьіѣa-z]+(?:-[А-ЯЁа-яёъьіѣ]+)*,\s")

# Строка-мусор: номер страницы, колонтитул, обрывки букв без смысла.
def is_junk(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if re.fullmatch(r"[\dIVXLУХШ\s.,|\-—_]+", s):  # «27», «ХИ», «— 12 —»
        return True
    letters = re.findall(r"[а-яё]", s)
    # длинная строка без пробелов и знаков — «[о иваиасисивнвинаннинини»
    if len(s) > 10 and " " not in s.strip("[ ") and not re.search(r"[,.()]", s):
        return True
    return len(letters) < 3 and len(s) < 8


GLUED = re.compile(
    r"(?:\)\.?|см\.\s+[^.]{2,40}\.)\s*\|?\s*"
    r"(?=[А-ЯЁ][а-яёъьі]+(?:-[А-ЯЁа-яёъьі]+)*,\s+[А-ЯЁа-яё])"
)


def split_glued(entry):
    parts, start = [], 0
    for m in GLUED.finditer(entry):
        if entry[m.end()] == entry[0]:  # фамилия на ту же букву раздела
            parts.append(entry[start:m.end()].rstrip(" |"))
            start = m.end()
    parts.append(entry[start:])
    return [p for p in parts if p]


def main():
    raw = SRC.read_text(encoding="utf-8-sig")
    raw = raw[raw.index(START_MARKER):]

    # 1) Абзацы: разделитель — пустая строка.
    paragraphs = re.split(r"\n\s*\n", raw)

    # 2) Чистим каждый абзац: убираем строки-мусор, склеиваем строки,
    #    снимаем переносы «Але- ксандро» -> «Александро».
    junk, texts = [], []
    for par in paragraphs:
        lines = [l for l in par.split("\n") if l.strip()]
        junk += [l for l in lines if is_junk(l)]
        kept = [l for l in lines if not is_junk(l)]
        if kept:
            text = " ".join(l.strip() for l in kept)
            text = re.sub(r"(\w)- (\w)", r"\1\2", text)
            texts.append(re.sub(r"\s+", " ", text).strip())

    # 3) Границы букв. Том 1 — буквы А–Г. Раздел следующей буквы начинается
    #    там, где 5 абзацев-кандидатов подряд начинаются с этой буквы:
    #    одиночная строка «Гизешаузенв, …» внутри раздела «В» границей не станет.
    alphabet = "АБВГ"
    cand = [i for i, t in enumerate(texts) if ENTRY_START.match(t)]
    section_start = {"А": 0}
    for letter in alphabet[1:]:
        for k in range(len(cand) - 4):
            if cand[k] > max(section_start.values()) and all(
                texts[cand[k + j]][0] == letter for j in range(5)
            ):
                section_start[letter] = cand[k]
                break

    def section_of(i):
        return max((s, l) for l, s in section_start.items() if s <= i)[1]

    # 4) Абзац — новая статья, если начинается с «Фамилия, » И с буквы
    #    своего раздела. Иначе это продолжение предыдущей статьи (разрыв
    #    страницы) или строка стихотворной эпитафии («Прохожий, чтя се…»).
    entries = []
    for i, text in enumerate(texts):
        if not entries or (ENTRY_START.match(text) and text[0] == section_of(i)):
            entries.append(text)
        else:
            entries[-1] += " " + text
    # Перенос мог прийтись на границу страницы: «19 де- | кабря» — склеиваем ещё раз.
    entries = [re.sub(r"(\w)- (\w)", r"\1\2", e) for e in entries]

    # 5) Иногда OCR не оставил пустой строки между статьями, и в одном абзаце
    #    оказалось несколько: «…кладбище). | Бобровъ, Яковъ …». Режем после
    #    «).» / «)» или после отсылки «— см. Альштремъ.», если дальше идёт
    #    «Фамилия, Имя» на ту же букву.
    entries = [part for e in entries for part in split_glued(e)]

    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "surname", "is_reference", "text"])
        for i, e in enumerate(entries, 1):
            surname = e.split(",", 1)[0]
            is_ref = bool(re.search(r"[—-]\s*см\.", e)) and len(e) < 120
            w.writerow([i, surname, int(is_ref), e])

    # Контроль: фамилии должны идти по алфавиту (сравниваем первые 2 буквы).
    # Нарушение = подозрение на склейку/разрыв статей или OCR-ошибку в фамилии.
    abc = "абвгдеёжзиійклмнопрстуфхцчшщъыьѣэюяѳ"
    def key(e):
        return [abc.find(ch) for ch in e[:2].lower()]
    order_breaks = [
        (i + 1, entries[i - 1][:40], entries[i][:60])
        for i in range(1, len(entries))
        if key(entries[i]) < key(entries[i - 1])
    ]
    letter_counts = {b: sum(1 for e in entries if e[0] == b) for b in alphabet}
    with REPORT.open("w", encoding="utf-8-sig") as f:
        f.write(f"Статей: {len(entries)}\n")
        f.write(f"Из них отсылок «см.»: "
                f"{sum(1 for e in entries if re.search(r'[—-]\s*см\.', e) and len(e) < 120)}\n")
        f.write(f"Выброшено строк-мусора: {len(junk)}\n")
        f.write(f"Статей по буквам: {letter_counts}\n")
        f.write(f"Нарушений алфавитного порядка: {len(order_breaks)}\n\n")
        for n, prev, t in order_breaks[:60]:
            f.write(f"  #{n}: [{prev}] -> [{t}]\n")
        f.write("\nПримеры выброшенного мусора:\n")
        for l in junk[:40]:
            f.write(f"  {l.strip()}\n")
    print(REPORT.read_text(encoding="utf-8-sig")[:1500])


if __name__ == "__main__":
    main()
