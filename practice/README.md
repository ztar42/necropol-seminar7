# Семинар 7. Вайб-кодинг — практическое задание

Источник: «Петербургский некрополь», т. 1 (А–Г), СПб., 1912 — OCR-текст с Internet Archive
(https://archive.org/details/peterburgskijnekropolt1ag60), сохраняется в `data/necropol_t1.txt`.

## Отчёты
- `reports/result.html` — для проверяющего (выполнение задания);
- `reports/explain.html` — для докладчика (подробные объяснения, инструкция по запуску, вопросы и ответы).
Открываются в любом браузере двойным щелчком.

## Запуск
Нужен Python 3.10+ (https://www.python.org/downloads/), сторонние библиотеки не нужны.
Команды выполняются из этой папки. На Windows пишите `python` вместо `python3`.

Всё одной командой (файл самодостаточен, его можно запускать и отдельно от проекта):

    python3 necropol_dates.py

Или по этапам:

    python3 code/download.py      # скачать источник (если файла ещё нет)
    python3 code/segment.py       # этапы 0–1: текст -> статьи (output/entries.csv)
    python3 code/dates_v1.py      # этап 3, наивная версия (для сравнения)
    python3 code/dates_v2.py      # этап 3, итоговая версия + контроль
    python3 code/evaluate.py                                           # эталон, 60 статей
    python3 code/evaluate.py output/dates.csv data/holdout_dates.csv   # отложенная выборка, 40 статей

Скачать источник вручную: https://archive.org/download/peterburgskijnekropolt1ag60/peterburgskijnekropolt1ag60_djvu.txt
→ сохранить как `data/necropol_t1.txt`.

## Промты для Claude Haiku
`prompts/haiku_prompts.md` — серия из 6 промтов для этапа «Даты», адаптированная для небольшой модели
(готовые данные, одно изменение на шаг, тесты в каждом промте). `prompts/dates_haiku.py` — код,
который Claude Haiku написала по этой серии (без правок). Запуск: `python3 prompts/dates_haiku.py`,
оценка: `python3 code/evaluate.py output/dates_haiku.csv data/holdout_dates.csv`.
