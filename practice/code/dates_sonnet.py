"""Извлечение дат рождения и смерти из статей «Петербургского некрополя» (простая версия).

Код написан моделью Claude Sonnet по серии промтов prompts/sonnet_prompts.md
(5 шагов), сохранён без правок (добавлен только этот абзац). Запуск из папки practice:
    python3 code/dates_sonnet.py
"""
import csv
import re
import sys

# Названия месяцев: сначала приставка слова, затем часть слова (для искажённых OCR вариантов:
# «юля», «поля», «1юня», «пюня», «апрфля», «апр$ля», «шоня» ...)
MONTH_PREFIX = [("янв", 1), ("фев", 2), ("мар", 3), ("апр", 4), ("мая", 5), ("май", 5),
                ("июн", 6), ("юн", 6), ("июл", 7), ("юл", 7), ("авг", 8), ("сен", 9),
                ("окт", 10), ("ноя", 11), ("дек", 12)]
MONTH_PART = [("янв", 1), ("февр", 2), ("март", 3), ("апр", 4), ("юн", 6), ("юл", 7),
              ("оня", 6), ("оля", 7), ("авг", 8), ("густ", 8), ("сент", 9), ("окт", 10), ("нояб", 11),
              ("дек", 12), ("кабр", 12)]

# год: 1500-1999 или искажённый OCR (13xx -> 18xx, «т852» -> 1852)
YEAR = r"(1[3-9]\d\d|[тТ]\d{3})"
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*(1?[^\d]{3,12}?)\s*" + YEAR + r"(?!\d)")
YEAR_RE = re.compile(r"(?<!\d)" + YEAR + r"(?!\d)")
BIRTH_MARK_RE = re.compile(r"[рРpP]\.\s*$")


def fix_year(y):
    if y[0] in "тТ":
        return "1" + y[1:]
    if y.startswith("13"):
        return "18" + y[2:]
    return y


def month_of(word):
    w = word.lower().replace("ѣ", "е").replace("ъ", "")
    w = re.sub(r"[^а-яё]", "", w).replace("і", "и")
    w = w.replace("i", "и")
    if w in ("ня", "пня"):  # «5 ня 1858»: от слова «июня» остался обрывок
        return 6
    for stem, num in MONTH_PREFIX:
        if w.startswith(stem):
            return num
    for part, num in MONTH_PART:
        if part in w:
            return num
    return None


def find_dates(text):
    """Список (начало, конец, дата-строка) в порядке следования."""
    found, pos = [], 0
    while pos < len(text):
        m = DATE_RE.search(text, pos)
        y = YEAR_RE.search(text, pos)
        if m and (not y or m.start() <= y.start() + 3):
            mon = month_of(m.group(2))
            day = int(m.group(1))
            if mon and 1 <= day <= 31:
                s = "%s-%02d-%02d" % (fix_year(m.group(3)), mon, day)
                found.append((m.start(), m.end(), s))
                pos = m.end()
                continue
            if mon:
                s = "%s-%02d" % (fix_year(m.group(3)), mon)
                found.append((m.start(), m.end(), s))
                pos = m.end()
                continue
        if y:
            found.append((y.start(), y.end(), fix_year(y.group(1))))
            pos = y.end()
        else:
            break
    return found


CEMETERY_WORDS = ("кладб", "лавр", "монаст", "церк", "пуст", "собор")
# слова, с которых начинается рассказ о родственниках / надписи (только с заглавной буквы)
RELATIVES_RE = re.compile(
    r"(?<=\s)(?:Жена|Мужъ|Сынъ|Дочь|Отецъ|Мать|Братъ|Сестра|Вдова|Тесть|Теща|Внукъ|"
    r"Дѣти|Дети|Съ|Сь|Отъ|Надпись)\b")
CROSS_RE = re.compile(r"(?:^|\s)[+{|}Тт1ф—†$ГЕ:\-]{1,3}(?=\s|$)")
BIRTH_WORD_RE = re.compile(r"(?<![^\W\d_])[рРpP]\.")
REF_RE = re.compile(r"[—-]\s*см\.")


def own_part(text):
    """Часть статьи, относящаяся к самому человеку: без кладбища и без родственников."""
    # отсылка в начале склеенной записи: «Иванова —см. Петрова. Сидорова, Анна, ...»
    m = REF_RE.search(text)
    if m and not YEAR_RE.search(text[:m.start()]):
        rest = text[m.end():]
        k = rest.find(". ")
        text = rest[k + 2:] if k >= 0 else ""
    # скобки: кладбище обрезаем, прочие (другое написание фамилии) выкидываем
    out, pos = "", 0
    for pm in re.finditer(r"\(([^()]*)(\)|$)", text):
        inner, closed = pm.group(1), pm.group(2)
        tail = text[pm.end():].strip(" .,;:")
        if not closed or not tail or any(w in inner.lower() for w in CEMETERY_WORDS):
            return cut_relatives(out + text[pos:pm.start()])
        out += text[pos:pm.start()] + " "
        pos = pm.end()
    return cut_relatives(out + text[pos:])


def cut_relatives(body):
    m = RELATIVES_RE.search(body)
    return body[:m.start()] if m else body


F_RANGE = "год вне диапазона"
F_ORDER = "рождение позже смерти"
F_OLD = "больше 110 лет"
F_AGE = "возраст не совпадает"
F_NODEATH = "есть год, но нет смерти"
NO_CROSS = "смерть без креста"
ALL_FLAGS = [F_RANGE, F_ORDER, F_OLD, F_AGE, F_NODEATH, NO_CROSS]
AGE_RE = re.compile(r"(?<![\d.])(\d{1,3})\s*(?:л\.|г\.|лѣт|лЪт|лет|лЬт)")


def check_flags(body, dates, birth, death, death_end):
    out = []
    by = int(birth[:4]) if birth else None
    dy = int(death[:4]) if death else None
    if any(y is not None and not 1700 <= y <= 1912 for y in (by, dy)):
        out.append(F_RANGE)
    if by and dy:
        if by > dy:
            out.append(F_ORDER)
        if dy - by > 110:
            out.append(F_OLD)
        m = AGE_RE.search(body[death_end:death_end + 30])
        if m and abs(int(m.group(1)) - (dy - by)) > 1:
            out.append(F_AGE)
    if dates and not death:
        out.append(F_NODEATH)
    return out


def extract(text, is_reference=False, flags=None):
    """Возвращает (birth, death). В flags (список) добавляет пометки для ручной проверки."""
    if is_reference:
        return "", ""
    body = own_part(text)
    dates = find_dates(body)
    if not dates:
        return "", ""
    birth = death = ""
    death_end = 0
    prev_end = 0
    for i, (st, en, d) in enumerate(dates):
        ctx = body[prev_end:st]
        prev_end = en
        has_birth = bool(BIRTH_WORD_RE.search(ctx))
        if has_birth:
            # крест после «р.» («р. 2 + 3 апрѣля», «р. 183...... + 1882»):
            # дата рождения нечитаема, а эта дата — дата смерти
            bm = list(BIRTH_WORD_RE.finditer(ctx))[-1]
            if CROSS_RE.search(ctx[bm.end():]):
                has_birth = False
        has_cross = bool(CROSS_RE.search(ctx))
        if i == 0:
            if has_birth:
                birth = d
            elif has_cross:
                death, death_end = d, en
                break
            elif len(dates) > 1 and CROSS_RE.search(body[en:dates[1][0]]):
                birth = d  # «Клара, 29 октября 1821 | 17 июля 1891» (нет «р.»)
            else:
                death, death_end = d, en
                break
        else:
            if has_cross:
                death, death_end = d, en
            elif (i + 1 < len(dates) and birth
                  and CROSS_RE.search(body[en:dates[i + 1][0]])):
                continue  # промежуточная дата (напр. свадьба), смерть — после креста
            elif len(ctx) <= 40 and not has_birth and birth:
                death, death_end = d, en
                if flags is not None:
                    flags.append(NO_CROSS)
            break
    if flags is not None:
        flags.extend(check_flags(body, dates, birth, death, death_end))
    return birth, death


SELF_TESTS = [
    ("Баженовъ, Иванъ Прокофьевичъ, р. 8 ноября 1791 + 8 января 1872 (Смоленское кладбище).", False,
     ("1791-11-08", "1872-01-08")),
    ("Боголюбовъ, Павелъ Николаевичъ + 28 декабря 1904 (Новодѣвичій монастырь).", False,
     ("", "1904-12-28")),
    ("Годенъ, Викторія + 28 поня 1905 (Католическое кладбище).", False, ("", "1905-06-28")),
    ("Брезинская, Юстина + 16 апрфля 1889 (Смоленское кладбище).", False, ("", "1889-04-16")),
    ("Гребне, Софія-Доротея, р. 12 марта 1816 1 26 января 1877 (Волково кладбище).", False,
     ("1816-03-12", "1877-01-26")),
    ("Гюне, баронъ Эдуардъ, р. 15 ноября 1852 1 5 марта 1856 (Волково кладбище).", False,
     ("1852-11-15", "1856-03-05")),
    ("Гельмгольцъ, Ѳедоръ, капитанъ, р. 1852 Т 1892 (Гатчинское кладбище).", False, ("1852", "1892")),
    ("Гамельманъ, Амалія, р. 9 февраля 1800 + 23 января 1336 (Волково кладбище).", False,
     ("1800-02-09", "1836-01-23")),
    ("Волкова, Марія Филипповна + 2 Февраля 1894 (Новодѣвичій монастырь).", False, ("", "1894-02-02")),
    ("Акорчевъ, Александръ, колл. сов. { 26 марта 1885, на 61 г. Жена: Вѣра Петровна 1 23 октября 1909 (Смоленское кладбище).",
     False, ("", "1885-03-26")),
    ("Банье, Андрей-Фридрихъ, р. въ Мекленбургъ-Шверинѣ 29 сентября 1769 + 27 апрѣля 1840, 70 л. (Волково кладбище).",
     False, ("1769-09-29", "1840-04-27")),
    ("Брюнъ-де-Сентъ-Ипполитъ, Елизавета, рожд. Дюлу (Бивоча) 1 5 февраля 1843, 34 л. (Смоленское кладбище).",
     False, ("", "1843-02-05")),
    ("Годенъ, Викторія, рожд. Вердье + 28 поня 1905, 71 г. (Католическое кладбище).", False, ("", "1905-06-28")),
    ("Вальдманъ, Елена, рожд. Шинна, р. въ Митавѣ 30 сентября 1799 т 1 мая 1875 (Гатчинское кладбище).",
     False, ("1799-09-30", "1875-05-01")),
    ("Аркъ-фанъ, Карлъ, р. 28 августа 1839 + 11 августа 1992 (Волково кладбище).", False,
     ("1839-08-28", "1992-08-11")),
    ("Авенарусъ, Владимръ Геормевичъ, р. 2 + 3 апрЪля 1878 (Свято-Троицкое кладбище въ Старомъ ПетергофЪ).",
     False, ("", "1878-04-03")),
    ("Глазовъ, Петръ Ивановичъ + 19 1юля 1903, на 61 г. (Волково православное кладбище).", False,
     ("", "1903-07-19")),
    ("Аксенова, Елизавета Ивановна—см. Анцъ.", True, ("", "")),
]


def self_check():
    for text, ref, expected in SELF_TESTS:
        flags = []
        got = extract(text, ref, flags)
        if text.startswith("Аркъ-фанъ") and not {F_RANGE, F_OLD} <= set(flags):
            sys.exit("САМОПРОВЕРКА НЕ ПРОЙДЕНА: пометки для Аркъ-фанъ: %r" % flags)
        if got != expected:
            sys.exit("САМОПРОВЕРКА НЕ ПРОЙДЕНА: %r -> %r, ожидалось %r" % (text, got, expected))
    print("Самопроверка пройдена (%d примеров)." % len(SELF_TESTS))


def main():
    self_check()
    with open("output/entries.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    n_birth = n_death = 0
    counts = dict.fromkeys(ALL_FLAGS, 0)
    review = []
    with open("output/dates_sonnet.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "birth", "death", "flags"])
        for r in rows:
            flags = []
            b, d = extract(r["text"], r["is_reference"] == "1", flags)
            flags = list(dict.fromkeys(flags))
            n_birth += bool(b)
            n_death += bool(d)
            for fl in flags:
                counts[fl] += 1
            if flags:
                review.append([r["id"], ";".join(flags), b, d, r["text"]])
            w.writerow([r["id"], b, d, ";".join(flags)])
    with open("output/dates_sonnet_review.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "flags", "birth", "death", "text"])
        w.writerows(review)
    n = len(rows)
    print("=== Сводка ===")
    print("Статей обработано: %d" % n)
    print("Дата рождения найдена: %d (%.1f%%)" % (n_birth, 100 * n_birth / n))
    print("Дата смерти найдена: %d (%.1f%%)" % (n_death, 100 * n_death / n))
    print("Помечено для проверки: %d (%.1f%%)" % (len(review), 100 * len(review) / n))
    for fl in ALL_FLAGS:
        print("  %s: %d" % (fl, counts[fl]))


if __name__ == "__main__":
    main()
