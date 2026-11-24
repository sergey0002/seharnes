# Прочитать и сообщить

Начни с адреса записи:

```bash
ttask show T-001
ttask show T-001 --mode full
# допустимы также body, comments, digest и handoff
ttask show T-001/C-3
ttask show T-001/AC-2
ttask show D-001
```

Режимы выбирают состав, но не режут выбранные тексты:

- `body` — тело без ленты;
- `full` — тело и вся лента;
- `comments` — вся лента;
- `digest` — тело и оглавление ленты;
- `handoff --last K` — тело, последние K и все `handoff`;
- `comment`/`T-NNN/C-N` — одна реплика;
- `element`/`T-NNN/AC-N` — один элемент;
- `report`/`D-NNN` — отчёт закрытия.

Размеры печатаются в знаках и байтах. Большой контекст выгрузи:

```bash
ttask digest T-001
ttask digest T-001 --part comments:1-5
# допустимы также body и toc
```

`digest.md` производен и устаревает после любой правки записи.
