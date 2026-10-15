# Семинар 7. Вайб-кодинг — практическое задание

Источник: «Петербургский некрополь», т. 1 (А–Г), СПб., 1912 — OCR-текст с Internet Archive
(https://archive.org/details/peterburgskijnekropolt1ag60), сохраняется в `data/necropol_t1.txt`.

Выбранный этап — извлечение дат рождения и смерти. Его код (`code/dates_haiku.py`) написала
модель Claude Haiku по серии из шести промтов (`prompts/haiku_prompts.md`).

## Отчёты
- `reports/result.html` — для проверяющего (выполнение задания);
- `reports/explain.html` — для докладчика (пояснения, инструкция по запуску, вопросы и ответы).
Открываются в любом браузере двойным щелчком.

## Запуск
Нужен Python 3.10+ (https://www.python.org/downloads/), сторонние библиотеки не нужны.
Команды выполняются из этой папки. На Windows пишите `python` вместо `python3`.

Всё одной командой (файл самодостаточен, его можно запускать и отдельно от проекта):

    python3 necropol_dates.py

Или по этапам:

    python3 code/download.py      # этап 0: скачать источник (если файла ещё нет)
    python3 code/segment.py       # этапы 0–1: текст -> статьи (output/entries.csv)
    python3 code/dates_haiku.py   # этап 3: даты + контроль (output/dates_haiku.csv, dates_haiku_review.csv)
    python3 code/evaluate.py                                                 # эталон, 60 статей
    python3 code/evaluate.py output/dates_haiku.csv data/holdout_dates.csv   # отложенная выборка, 40 статей

Скачать источник вручную: https://archive.org/download/peterburgskijnekropolt1ag60/peterburgskijnekropolt1ag60_djvu.txt
→ сохранить как `data/necropol_t1.txt`.
