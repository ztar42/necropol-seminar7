"""
Этап 3, версия 2: даты рождения и смерти, указанный возраст.
Учитывает искажения OCR и содержит механизмы контроля.

История правок (после каждой — прогон и сверка с контролем):
  итерация 2 — шаблоны месяцев/знака смерти по частотам OCR-искажений;
  итерация 3 — слова между знаком и датой, двойные даты, возраст только сразу
               после даты смерти, «т» внутри слова не знак, регистр «Февраля»;
  итерация 4 — граница «своей» части статьи только по скобке с местом
               погребения; «рожд.» = «урождённая».

Вход:  output/entries.csv  (результат этапа 1, segment.py)
Выход: output/dates.csv          — по строке на статью
       output/dates_review.csv   — статьи, которые надо посмотреть глазами
       output/dates_report.txt   — сводка контроля
"""
import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "output" / "entries.csv"
OUT = ROOT / "output" / "dates.csv"
REVIEW = ROOT / "output" / "dates_review.csv"
REPORT = ROOT / "output" / "dates_report.txt"

# ---------------------------------------------------------------------------
# 1. Месяцы. Каждый месяц — шаблон, который ловит и правильное написание,
#    и типичные искажения OCR (они собраны частотным подсчётом по корпусу):
#    «іюля» -> «юля», «поля», «1юля», «тюля»; «апрѣля» -> «апрЪля», «апрфля»,
#    «апр$ля»; «іюня» -> «поня», «1юня», «пюня», «шоня» …
# ---------------------------------------------------------------------------
I_NOISE = r"[1!|{(тпшгнШТІі'№‘]?"          # то, во что OCR превратил «і»
MONTH_PATTERNS = {
    1: r"ян\S?[ая]ря",                     # января, янзаря, янвяря
    2: r"ф?февраля",
    3: r"марта",
    4: r"апр\S{0,3}ля",                    # апрЪля, апрфля, апр$ля, апръфля
    5: r"мая",
    6: rf"{I_NOISE}[юо]{{0,2}}ня",          # юня, поня, 1юня, пюня, шоня, ня
    7: rf"{I_NOISE}[юо]{{0,2}}ля",          # юля, поля, 1юля, тюля, оля, ля
    8: r"а[вз]\S?уста",                     # августа, авлуста, азгуста
    9: r"сен\S?тября",                     # сентября, сенгября
    10: r"о[кя]\S?тября",                  # октября, окгября, оятября
    11: r"но\S?я\S?бря|нояря",             # ноября, нояабря
    12: r"дек?абря",
}
MONTH_ANY = "|".join(f"(?:{p})" for p in MONTH_PATTERNS.values())

# День: 1–2 цифры; «т», «|», «l» на месте единицы.
# «15/27 ноября» — дата по старому/новому стилю: берём старый (первый).
DAY = r"[\dт|l]{1,3}(?:/\d{1,2})?"
# Год: 4 знака из цифр и «т»/«з» (OCR путает 1 -> т, 3 -> з); «17..» — год
# неразборчив в самом издании.
YEAR = r"[\dтз]{2}[\dтз.]{2}"

YEAR_END = r"(?=[\s,.;:)]|$)"  # после года — пробел, знак препинания или конец
DATE_FULL = rf"(?:({DAY})\s+)?({MONTH_ANY})\.?\s+({YEAR}){YEAR_END}"
DATE_YEAR_ONLY = rf"({YEAR}){YEAR_END}"
# Между знаком и датой может стоять место или пояснение:
# «р. въ Ригѣ 9 апрѣля», «+ убитъ 12 октября», «+ въ Дрезденѣ 1833».
# Слово-вставка не может само быть знаком смерти («Т», «-»).
GAP = r"(?:(?![Ттф—\-]{1,2}\s)[^\d\s+†{|(]\S*\s+){0,2}?"

# Знак смерти «†». В OCR: + 1 | Т т { - — ф и их сочетания («+1», «{|»).
# Одиночная «1» считается знаком, только если после неё пробел:
# «1 5 марта» = † 5 марта, а «15 марта» — просто 15 марта.
# Знак не может стоять внутри слова: иначе «т» из «октября» станет «†».
DEATH_MARK = r"(?<!\w)(?:[+†{|Ттф—\-]{1,2}(?=[\s\d])|1(?=\s))"
# «р.» — родился; «рожд.» обычно значит «урождённая» (рожд. Соймонова),
# поэтому после «рожд.» дата должна идти сразу, без слов-вставок.
BIRTH_MARK = rf"(?<!\w)(?:[рР]\.\s*{GAP}|рожд\.\s*)"

# re.I: месяц бывает с заглавной буквы («4 Февраля 1884»).
BIRTH_RE = re.compile(rf"{BIRTH_MARK}(?:{DATE_FULL}|{DATE_YEAR_ONLY})", re.I)
DEATH_RE = re.compile(rf"{DEATH_MARK}\s*{GAP}(?:{DATE_FULL}|{DATE_YEAR_ONLY})", re.I)
# Дата без знака — запасной вариант, если знак смерти съеден OCR.
BARE_RE = re.compile(rf"(?<!\S){DATE_FULL}", re.I)

# Указанный возраст: «на 45 г.», «на 2г.», «63 л.», «43 лЬтъ», «73 г.»
# Берём возраст только сразу после даты смерти — иначе попадается возраст
# внучки («на 2 г.») или стаж службы («болѣе 40 лѣтъ»).
AGE_RE = re.compile(r"\s*[,;.]?\s*(?:на\s*)?(\d{1,3})\s*(?:-?м[ъь]\s*)?(?:г\.|г(?=\W)|л\.|л[ЬЪБъь]т|год)")

# Где кончается «своя» часть статьи и начинаются родственники/место погребения.
# Даты после этой границы принадлежат другим людям.
SCOPE_END = re.compile(
    # Скобка с местом погребения: «(Волково…», OCR: «{Смоленское…». Другие
    # скобки («рожд. Дюлу (Бивоча)», «19 сентября (1 октября)») — не граница.
    r"(?:(?:\(|\{(?=[А-ЯЁ]))(?=[^)]{0,80}(?:кладбищ|лавр|монастыр|пустын|собор|церк|[Сс]ел[ЪЬоа]))"
    r"|\b(?:Жена|Мужъ|Мужь|Дочь|Сынъ|Дѣти|Внучка|Внукъ|Надпись)\b"
    r"|\bС[ъЪь]\s+[А-ЯЁ])"                    # «Съ М. И. Аксеновой»
)

YEAR_MIN, YEAR_MAX = 1700, 1912  # том издан в 1912 г.


def norm_year(s):
    """«т852» -> 1852, «1336» -> 1836 (OCR: 8 -> 3), «17..» -> None."""
    if s is None or "." in s:
        return None
    s = s.replace("т", "1").replace("з", "3")
    if not s.isdigit():
        return None
    y = int(s)
    if 1300 <= y < 1400:          # в корпусе нет XIV века: это 18xx
        y += 500
    return y


def norm_day(s):
    if not s:
        return None
    s = s.split("/")[0].replace("т", "1").replace("|", "1").replace("l", "1")
    if not s.isdigit():
        return None
    d = int(s)
    if d > 31 and s.startswith("1"):  # «115» = знак «1» + день 15
        d = int(s[1:])
    return d if 1 <= d <= 31 else None


def norm_month(s):
    if not s:
        return None
    for num, pat in MONTH_PATTERNS.items():
        if re.fullmatch(pat, s, flags=re.I):
            return num
    return None


def parse(m):
    """Match -> (день, месяц, год). Группы: день, месяц, год | год-только."""
    if m is None:
        return (None, None, None)
    day, month, year = m.group(1), m.group(2), m.group(3)
    year_only = m.group(4) if m.re.groups >= 4 else None
    if year_only:
        return (None, None, norm_year(year_only))
    return (norm_day(day), norm_month(month), norm_year(year))


def iso(d):
    day, month, year = d
    if year is None:
        return ""
    s = str(year)
    if month:
        s += f"-{month:02d}"
        if day:
            s += f"-{day:02d}"
    return s


def extract(text):
    """Возвращает словарь с датами и флагами для одной статьи."""
    # Отрезаем фамилию с запятой, чтобы не путать её с датами.
    body = text.split(",", 1)[1] if "," in text else text
    cut = SCOPE_END.search(body)
    scope = body[:cut.start()] if cut else body

    b = BIRTH_RE.search(scope)
    birth = parse(b)

    # Смерть ищем после даты рождения (если она есть).
    after = scope[b.end():] if b else scope
    d = DEATH_RE.search(after)
    death = parse(d)
    source = "mark" if d else ""
    bare = None
    if death[2] is None:
        bare = BARE_RE.search(after)
        if bare:
            death = parse(bare)
            source = "bare"
        if death[2] is None:
            bare = None

    a = AGE_RE.match(after[(d or bare).end():]) if (d or bare) else None
    age = int(a.group(1)) if a else None

    flags = []
    by, dy = birth[2], death[2]
    for name, y in (("birth", by), ("death", dy)):
        if y is not None and not (YEAR_MIN <= y <= YEAR_MAX):
            flags.append(f"{name}_year_out_of_range")
    if by and dy:
        calc = dy - by
        if calc < 0:
            flags.append("birth_after_death")
        elif calc > 110:
            flags.append("age_over_110")
        if age is not None and abs(calc - age) > 1:
            flags.append("age_mismatch")
    if dy is None and re.search(r"\b1[6-9]\d\d\b", scope):
        flags.append("year_present_but_no_death")
    if source == "bare":
        flags.append("death_without_mark")

    return {
        "birth": iso(birth), "death": iso(death), "age_stated": age,
        "age_calc": (dy - by) if (by and dy) else None,
        "flags": ";".join(flags), "scope": scope,
    }


def main():
    rows = list(csv.DictReader(IN.open(encoding="utf-8-sig")))
    results = []
    for r in rows:
        res = extract(r["text"])
        res.update(id=r["id"], surname=r["surname"], is_reference=r["is_reference"])
        results.append(res)

    cols = ["id", "surname", "is_reference", "birth", "death",
            "age_stated", "age_calc", "flags"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    # ---- Контроль ---------------------------------------------------------
    base = [r for r in results if r["is_reference"] == "0"]
    n = len(base)
    with_death = sum(1 for r in base if r["death"])
    with_birth = sum(1 for r in base if r["birth"])
    full_death = sum(1 for r in base if len(r["death"]) == 10)
    with_age = sum(1 for r in base if r["age_stated"] is not None and r["age_calc"] is not None)
    age_ok = sum(1 for r in base if r["age_stated"] is not None and r["age_calc"] is not None
                 and "age_mismatch" not in r["flags"])
    flag_counts = Counter(f for r in base for f in r["flags"].split(";") if f)

    review = [r for r in base if r["flags"] and r["flags"] != "death_without_mark"]
    with REVIEW.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols + ["scope"], extrasaction="ignore")
        w.writeheader()
        w.writerows(review)

    pct = lambda x: f"{x} ({100 * x / n:.1f}%)"
    lines = [
        f"Статей (без отсылок «см.»): {n}",
        f"Найдена дата смерти:      {pct(with_death)}",
        f"  из них полная (д-м-г):  {pct(full_death)}",
        f"Найдена дата рождения:    {pct(with_birth)}",
        f"Возраст указан и посчитан: {with_age}; совпадает (±1 год): "
        f"{age_ok} ({100 * age_ok / max(with_age, 1):.1f}%)",
        "",
        "Флаги контроля:",
        *[f"  {k}: {v}" for k, v in flag_counts.most_common()],
        "",
        f"На ручную проверку (output/dates_review.csv): {len(review)}",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
