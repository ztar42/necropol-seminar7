"""Извлечение дат рождения и смерти из OCR-текста справочника «Петербургский некрополь».

Код написан моделью Claude Haiku по серии промтов prompts/haiku_prompts.md
(6 шагов), сохранён без правок (добавлен только этот абзац). Запуск из папки practice:
    python3 code/dates_haiku.py
Только стандартная библиотека, совместимо с Python 3.10.
"""

import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
IN_PATH = BASE_DIR / "output" / "entries.csv"
OUT_PATH = BASE_DIR / "output" / "dates_haiku.csv"
REVIEW_PATH = BASE_DIR / "output" / "dates_haiku_review.csv"

FLAG_NAMES = [
    "birth_year_out_of_range",
    "death_year_out_of_range",
    "birth_after_death",
    "age_over_110",
    "year_present_but_no_death",
]

# Номер месяца -> шаблон регулярного выражения (OCR-искажения допускаются).
MONTH_PATTERNS = {
    1: r"ян\S?[ая]ря",
    2: r"ф?февраля",
    3: r"марта",
    4: r"апр\S{0,3}ля",
    5: r"мая",
    6: r"[1!|{(тпшгнШТІі'№‘]?[юо]{0,2}ня",
    7: r"[1!|{(тпшгнШТІі'№‘]?[юо]{0,2}ля",
    8: r"а[вз]\S?уста",
    9: r"сен\S?тября",
    10: r"о[кя]\S?тября",
    11: r"но\S?я\S?бря|нояря",
    12: r"дек?абря",
}


def norm_month(word):
    for number, pattern in MONTH_PATTERNS.items():
        if re.fullmatch(pattern, word, re.I):
            return number
    return None


def norm_year(s):
    s = s.lower().replace("т", "1").replace("з", "3")
    if "." in s or not s.isdigit() or len(s) != 4:
        return None
    year = int(s)
    if 1300 <= year <= 1399:  # OCR путает 8 и 3: 1336 -> 1836
        year += 500
    return year


def norm_day(s):
    s = s.lower().replace("т", "1").replace("|", "1").replace("l", "1")
    if "/" in s:
        s = s.split("/")[0]
    if not s.isdigit():
        return None
    day = int(s)
    if day > 31 and str(day).startswith("1"):  # 115 -> 15
        day = int(str(day)[1:])
    if not 1 <= day <= 31:
        return None
    return day


_MONTH_ALT = "|".join(f"(?:{p})" for p in MONTH_PATTERNS.values())

# Знак смерти: не внутри слова; «1» — знак только если после неё пробел.
DEATH_MARK = r"(?<!\w)(?:[+†{|Ттф—\-]{1,2}(?=[\s\d])|1(?=\s))"

# Слово между меткой и датой: не с цифры, не со знака смерти.
WORD = r"(?!(?:[\d+†{|—\-]|[Ттф1](?!\w)))[^\s,(){}]+"
WORDS = r"(?:" + WORD + r"\s+){0,2}"

# Граница «своей» части: родственники, «Съ ...», скобки с местом захоронения.
_BRACKET_RE = re.compile(r"[({][А-ЯЁІѢѲA-Z]")
_PLACE_WORDS = ("кладбищ", "лавр", "монастыр", "пустын", "собор", "церк", "сел")
_STOP_RE = re.compile(
    r"(?<!\w)(?:Жена|Мужъ|Дочь|Сынъ|Внучка|Надпись)(?!\w)|(?<!\w)Съ (?=[А-ЯЁ])"
)
_YEAR_IN_PART_RE = re.compile(r"(?<!\d)1[6-9]\d\d(?!\d)")


def _own_end(text, start):
    ends = [len(text)]
    for m in _BRACKET_RE.finditer(text, start):
        window = text[m.start():m.start() + 80]
        close = window.find(")")
        if close != -1:
            window = window[:close]
        if any(word in window.lower() for word in _PLACE_WORDS):
            ends.append(m.start())
            break
    stop = _STOP_RE.search(text, start)
    if stop:
        ends.append(stop.start())
    return min(ends)


def _date_re(prefix):
    # prefix: метка перед датой. Дата: [день месяц] год. День без месяца не допускается.
    return re.compile(
        prefix
        + r"(?:(?P<day>[\dТтl|/]{1,6})\s+(?P<month>"
        + _MONTH_ALT
        + r")(?:\s*\([^()]{1,30}\))?\s+)?(?P<year>[\dТтз.]{4})(?![\dТтз])",
        re.I,
    )


# «р.» допускает до двух слов перед датой; «рожд.» — только дату сразу после метки.
_BIRTH_RE = _date_re(r"(?:(?<!\w)р\.\s*" + WORDS + r"|(?<!\w)рожд\.\s*)")
_DEATH_RE = _date_re(DEATH_MARK + r"\s*" + WORDS)


def _format(match):
    if match is None:
        return ""
    year = norm_year(match.group("year"))
    if year is None:
        return ""
    if match.group("month") is None:
        return f"{year:04d}"
    month = norm_month(match.group("month"))
    day = norm_day(match.group("day"))
    if day is None:
        return f"{year:04d}-{month:02d}"
    return f"{year:04d}-{month:02d}-{day:02d}"


def _year(date_str):
    return int(date_str.split("-")[0]) if date_str else None


def _flags(part, birth, death):
    flags = []
    by, dy = _year(birth), _year(death)
    if by is not None and not 1700 <= by <= 1912:
        flags.append("birth_year_out_of_range")
    if dy is not None and not 1700 <= dy <= 1912:
        flags.append("death_year_out_of_range")
    if by is not None and dy is not None:
        if by > dy:
            flags.append("birth_after_death")
        if dy - by > 110:
            flags.append("age_over_110")
    if not death and _YEAR_IN_PART_RE.search(part):
        flags.append("year_present_but_no_death")
    return flags


def extract(text):
    # Работаем только со «своей» частью статьи: после фамилии и до родственников.
    start = text.find(",") + 1
    part = text[start:_own_end(text, start)]
    birth_match = _BIRTH_RE.search(part)
    death_start = birth_match.end() if birth_match else 0
    birth = _format(birth_match)
    death = _format(_DEATH_RE.search(part, death_start))
    return {"birth": birth, "death": death, "flags": _flags(part, birth, death)}


def _bd(text):
    result = extract(text)
    return {"birth": result["birth"], "death": result["death"]}


def self_test():
    assert _bd("Баженовъ, Иванъ Прокофьевичъ, р. 8 ноября 1791 + 8 января 1872 (Смоленское кладбище).") == {"birth": "1791-11-08", "death": "1872-01-08"}
    assert _bd("Боголюбовъ, Павелъ Николаевичъ + 28 декабря 1904 (Новодѣвичій монастырь).") == {"birth": "", "death": "1904-12-28"}
    assert _bd("Аксенова, Елизавета Ивановна—см. Анцъ.") == {"birth": "", "death": ""}
    assert extract("Годенъ, Викторія + 28 поня 1905 (Католическое кладбище).")["death"] == "1905-06-28"
    assert extract("Глазовъ, Петръ Ивановичъ + 19 1юля 1903, на 61 г. (Волково кладбище).")["death"] == "1903-07-19"
    assert extract("Брезинская, Юстина + 16 апрфля 1889 (Смоленское кладбище).")["death"] == "1889-04-16"
    assert extract("Волкова, Марія Филипповна + 2 Февраля 1894 (Новодѣвичій монастырь).")["death"] == "1894-02-02"
    assert _bd("Гребне, Софія-Доротея, р. 12 марта 1816 1 26 января 1877 (Волково кладбище).") == {"birth": "1816-03-12", "death": "1877-01-26"}
    assert _bd("Гюне, баронъ Эдуардъ, р. 15 ноября 1852 1 5 марта 1856 (Волково кладбище).") == {"birth": "1852-11-15", "death": "1856-03-05"}
    assert _bd("Гельмгольцъ, Ѳедоръ, капитанъ, р. 1852 Т 1892 (Гатчинское кладбище).") == {"birth": "1852", "death": "1892"}
    assert _bd("Алексѣевъ, Сергѣй, р. 4 юля 1805 Т 10 ноября 1853 (Волково кладбище).") == {"birth": "1805-07-04", "death": "1853-11-10"}
    assert extract("Гамельманъ, Амалія, р. 9 февраля 1800 + 23 января 1336 (Волково кладбище).")["death"] == "1836-01-23"
    assert extract("Гюльпенъ, Францискъ, р. 16 ноября 1818 т 3 ноября 1863 (Католическое кладбище).")["death"] == "1863-11-03"
    assert extract("Акорчевъ, Александръ, колл. сов. { 26 марта 1885, на 61 г. Жена: Вѣра Петровна 1 23 октября 1909 (Смоленское кладбище).")["death"] == "1885-03-26"
    assert _bd("Банье, Андрей-Фридрихъ, р. въ Мекленбургъ-Шверинѣ 29 сентября 1769 + 27 апрѣля 1840, 70 л. (Волково кладбище).") == {"birth": "1769-09-29", "death": "1840-04-27"}
    assert extract("Брюнъ-де-Сентъ-Ипполитъ, Елизавета, рожд. Дюлу (Бивоча) 1 5 февраля 1843, 34 л. (Смоленское кладбище).")["death"] == "1843-02-05"
    assert extract("Годенъ, Викторія, рожд. Вердье + 28 поня 1905, 71 г. (Католическое кладбище).")["birth"] == ""
    assert _bd("Вальдманъ, Елена, рожд. Шинна, р. въ Митавѣ 30 сентября 1799 т 1 мая 1875 (Гатчинское кладбище).") == {"birth": "1799-09-30", "death": "1875-05-01"}
    r = extract("Аркъ-фанъ, Карлъ, р. 28 августа 1839 + 11 августа 1992 (Волково кладбище).")
    assert "death_year_out_of_range" in r["flags"] and "age_over_110" in r["flags"]


def main():
    with IN_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    results = []
    for row in rows:
        results.append((row, extract(row["text"])))

    with OUT_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "birth", "death", "flags"])
        writer.writeheader()
        for row, r in results:
            writer.writerow({"id": row["id"], "birth": r["birth"], "death": r["death"], "flags": ";".join(r["flags"])})

    with REVIEW_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "birth", "death", "flags", "text"])
        writer.writeheader()
        for row, r in results:
            if r["flags"]:
                writer.writerow({"id": row["id"], "birth": r["birth"], "death": r["death"],
                                 "flags": ";".join(r["flags"]), "text": row["text"]})

    # Сводка
    non_ref = [r for row, r in results if row["is_reference"].strip() == "0"]
    n = len(non_ref)
    with_death = sum(1 for r in non_ref if r["death"])
    with_birth = sum(1 for r in non_ref if r["birth"])
    flagged = sum(1 for row, r in results if r["flags"])

    def pct(x):
        return 100 * x / n if n else 0.0

    print(f"Статей всего: {len(rows)}, с флагами: {flagged}")
    print(f"Статей без отсылок (is_reference = 0): {n}")
    print(f"  с датой смерти: {with_death} ({pct(with_death):.1f}%)")
    print(f"  с датой рождения: {with_birth} ({pct(with_birth):.1f}%)")
    print("Флаги (по всем статьям):")
    for name in FLAG_NAMES:
        count = sum(1 for _, r in results if name in r["flags"])
        print(f"  {name}: {count}")


if __name__ == "__main__":
    self_test()
    main()
