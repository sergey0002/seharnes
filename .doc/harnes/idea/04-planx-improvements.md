# Доработки prepare-plan: sibling-дифы, миграции эпика, per-type проверки (не внедрены)

<!-- meta
type: plan
status: draft
updated: 2026-10-02
related: [../index.md, ./01-roadmap-hpta.md, ./03-plan-audit-x3.md, ../state/08-plan-contour.md]
tags: [harness, prepare-plan, sibling, migrations, pending]
-->

---

## Суть

План доработок prepare-plan по итогам stage2 пакета CT-2568 (задачи 2519,
2553, 2554, 2555, 2556), черновик 2026-10-01. НЕ внедрен: в SKILL.md нет
Epic exception в P0.5, нет сверки миграций в P2.3, нет Registry key coverage
в P2.7, нет fallback-явности и down-гейта (проверено 2026-10-02, якоря
не изменены).

---

Пять stage2 пакета CT-2568 (задачи 2519, 2553, 2554, 2555, 2556) устраняли расхождения,
которые можно было поймать на этапе исходных планов. Дифы sibling-задач маленькие
(6-13 файлов, 40-260 добавленных строк), посмотреть дешево. Мешал cost gate
в prepare-plan P0.5: полный `diff.md` соседа разрешен только при пересечении
с текущим Patches scope, а все находки stage2 лежали вне исходного scope. Предложения
точечные правки канона с опорой на существующие инструменты: task-diff.ps1,
find-related-tasks.ps1, `jsondoc.py search` и related и get, file-to-tasks.tsv,
`git ls-remote`, проверка имен миграций по веткам эпика.

Инвентарь (проверено 2026-10-01): task-diff.ps1 диф любой задачи без переключения
ветки (`generate` и `inspect`, параметры `-TaskNumber -Action`,
`.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1`). find-related-tasks.ps1 задачи
по arch-документу score JSON (`.agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1 -Doc payments.md
-Json -Limit 12`). `jsondoc.py search` поиск по тексту тегам файлам задачам
(`search --text X --tag Y --file path --tasks 2519,2553 --limit N`). `jsondoc.py related`
связанные задачи (`related --arch payments --profile legacy-v1`, `related --task 2519`).
`jsondoc.py get` точечное чтение (`get --task 2553 --select /files`, `get --arch payments`).
file-to-tasks.tsv индекс файл в задачи (954 строки,
`.doc/tasks/_map/file-to-tasks.tsv`, пересборка `build-tasks-index.ps1 -AlsoTsv`).
History планов история провалов prepare-plan. gototask.ps1 inspect ветки задачи
на origin релиз из Jira. `git ls-remote` проверка живых веток без гаданий
(`git ls-remote origin "refs/heads/*{N}*"` в кавычках).

Диагноз 4 точки. D1 cost gate запрещает читать чужие дифы: якорь prepare-plan SKILL.md
раздел P0.5 правило Diff order (`diff.files.md` first, full `diff.md` only for files
that overlap the current Patches scope, Never Read a related full diff just in case).
Все находки stage2 вне исходного Patches: YaApiService.php не патчился (общий B2C-путь
считался достаточным), а ShortCreate для новых типов отсутствовал; payments.js
и one-click-payment-modal.js не патчились (fallback `return item.name` считался
достаточным), а явных записей не было; newdesign.css патчился добавлением в общую
группу, а картинка под селектором не проверялась; `down()` миграций копировался
с условиями без проверки отката после активации. Раз файл вне scope, агент по скилу
не имел права открывать полный диф соседа.

D2 нет сверки sibling-веток эпика: P0.5b требует git-task-blame точного диапазона
и ls-remote на существование ветки, но не требует сравнить содержимое открытых веток
с общим parent. Коллизия `sql/migrations/Version20261001120000.php` в 2554 и 2555
невидима для обоих планов. Валидатор validate_plan.py ловит open branch без IN и OUT,
но не коллизию имен новых файлов.

D3 нет per-type проверки веток общего сервиса: бриф всех пяти задач требует записи
в `ct_paymentRequestLog`. Код пишет ShortCreate только в ветке `b2b_sberbank`
(`lib/Objects/Ymlog/YaApiService.php`). Планы записали общий обработчик покрывает
и не проверили отсутствие ветки для `sberbank`, `alfa_pay`, `sbp`, `tinkoff_bank`.
Пункта для каждого нового ключа проверить все ветки readers карты в P2.7 и P3 нет.

D4 UI-мелочи приняты на веру через fallback: словари имеют fallback на `item.name`,
иконки общую группу селекторов. Планы решили что явная запись не нужна, без
зафиксированного решения fallback ок. Гейта явности для новых кодов нет.

Предложения только план без внедрения. X1 Epic-scoped чтение sibling-дифов (снятие
cost gate для эпика): триггер у текущей задачи есть parent (поле Parent в task.md,
у нас CT-2568 у всех пяти) или P0.5a вернул 2 плюс задач с score 40 и выше по тем же
доменным docs. Правило: для каждой sibling-задачи эпика обязательно task-diff.ps1
`-TaskNumber M -Action generate` при устаревшем diff.md (проверка свежести
task-коммиты и SHA из метаданных diff.md против git), прочитать diff.files.md целиком,
прочитать полный diff.md целиком (исключение из cost gate только для эпика, не для всех
задач проекта). Якорь правки prepare-plan SKILL.md P0.5 блок Diff order. After добавить
подпункт Epic exception с триггером и списком прочитанного в Related tasks. Валидатор
не трогать (проверка чтением при P7.4a затруднена), достаточно чек-пункта P7
sibling-дифы эпика прочитаны или N/A с причиной. Стоимость 4-5 дифов по 40-260 строк,
все локально через task-diff, без сети при свежем fetch. Fallback при недоступном
origin local-fallback режим task-diff зафиксировать в плане.

X2 сверка имен новых миграций по веткам эпика (обязательно): определение открытая ветка
(снимает вопрос): ветка открыта если tip не входит в релиз. Проверка детерминированно:
`git fetch origin`, `git ls-remote origin "refs/heads/*{M}*"`,
`git log --oneline releases/5.7.4..origin/features/#M -- sql/migrations/ | head`.
Если вторая команда непуста, ветка M открыта относительно релиза. Альтернатива одной
командой `git branch -r --no-merged releases/5.7.4`. Правило: когда план создает новый
файл `sql/migrations/Version*.php`, агент обязан собрать basenames миграций
из scope-файлов всех открытых веток эпика
(`git diff --name-only releases/5.7.4...origin/features/#M -- sql/migrations/`)
и сверить с новым именем. Совпадение блок `status: ready`, переименование до P7.
Якорь правки prepare-plan SKILL.md P2.3 (Data) плюс P7 post-check одна строка. Плюс
опциональный скрипт `check-migration-collision.py` (stdlib, exit 0, 1, 2 по контракту
harness-improvement) только если ручная сверка даст повторные ошибки. Сначала текст,
скрипт вторым шагом при рецидиве. Стоимость 1 fetch плюс N ls-remote и diff-name-only,
дешево. Покрывает коллизию 2554 и 2555 и будущие случаи.

X3 эффективное использование поиска (TSV плюс jsondoc search): сейчас P0.5a использует
только find-related-tasks.ps1 (arch в задачи), а TSV и `search --file` и `--tag` и `--text`
подключаются поздно (after Patches paths known). Предложение поднять их в P0.5
обязательным веером для задач эпика: для каждого кандидата Patches и каждого файла
из sibling diff.files.md `grep "^path\t" .doc/tasks/_map/file-to-tasks.tsv` (кто уже
трогал файл), `python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py search --file {path} --limit 12`
и при нужде `--tag payment --tag-mode any`, `related --task {sibling}` для добора связей
которых нет в arch-индексе. Якорь правки ADAPTERS.local.md раздел Docs discovery order
пункты 3-4. After добавить готовые команды TSV и search с примером по payments.js.
Не новый инструмент, а перенос существующего в раннюю фазу. Стоимость локальные вызовы,
токены только на сводку (id, score, причина), полные doc.md соседей читать только
при score 40 и выше или file-overlap.

X4 per-key проверка readers карты (универсальная замена per-type логирования): вместо
продуктового гейта проверь ShortCreate для каждого типа универсальное правило для любой
карты-реестра (config map дискриминатора). Когда план добавляет новый ключ в карту
(у нас `newcodes`, в другом проекте любой `type -> handler` map), агент обязан найти
всех readers карты (Grep имени карты плюс Tier 3 full-text), для каждого reader
перечислить ветки switch и if по значению, в плане одной строкой на reader новый ключ
покрыт веткой X и падает в default Y и не покрыт (тогда патч или явный N/A с причиной
из кода). Закрывает ShortCreate (R1 всех stage2), confirmation и receipt ветки
и будущие карты без привязки к платежам. Якорь P2.7 Shared helper абзац, добавить
подпункт Registry key coverage. Валидатор мягкий чек по слову newcodes-подобному
маркеру не делать универсально, достаточно P7 пункта.

X5 отклонено продуктовые гейты getNameByItem и CSS (неуниверсально): явная запись
в getNameByItem и отдельный CSS-селектор с проверкой пути иконки для каждого нового
кода продуктовые детали платежного UI. В core prepare-plan не встраивать: номера задач,
имена JS-карт и CSS-селекторов непереносимы (нарушает контракт harness-improvement
о непродуктовом core). Замена универсальная уже покрыта X4 частично: gate явности
fallback. Если новый код опирается на fallback (default ветка, `return item.name`,
общая CSS-группа), план обязан зафиксировать решение одной строкой fallback ок
для кода X потому что с file и line fallback. Молчаливый fallback без строки P7 fail.
Ловит словари и иконки без хардкода имен. Дополнительно универсально gate `down()`
миграций: если `down()` содержит условия по флагам состояния (`AND isActive = 0 ...`),
план обязан ответить удалится ли запись после активации админом. Копипаст условий
без ответа P7 fail. Закрывает R3 stage2 2519, 2555, 2556 без продуктовой привязки.

Порядок внедрения предложение: 1 X1 epic exception в P0.5 плюс P7 пункт (только текст
SKILL, без скриптов). 2 X2 сверка миграций в P2.3 плюс P7 пункт (текст, скрипт только
при рецидиве). 3 X3 команды TSV и search в ADAPTERS.local.md (одна секция с примерами).
4 X4 registry key coverage в P2.7 плюс P7 пункт (текст). 5 X5 fallback-явность
и down-gate в P2.8 и P2.3 плюс P7 пункты (текст). 6 После каждого тест триггера
(поиск по тексту SKILL), validate_rules.py, parity представлений, sync из канона,
продуктовый код не трогать. 7 Проверки по контракту harness-improvement: scope small,
каждый пункт отдельно, откат удалением добавленных пунктов без чужих правок.

Сознательно не предлагается: новый обязательный скрипт чтения всех дифов для всех
задач (только эпик-триггер, иначе рост стоимости на trivial задачах); хардкод
getNameByItem, CSS-селекторов, ShortCreate, newcodes в core скила (непереносимо,
противоречит правилу канона); обязательный полный diff.md соседей без stale-проверки
(сначала свежесть метаданных diff, затем чтение); изменение P7 в machine-валидатор
для новых пунктов (текстовые чек-пункты достаточно, machine-гейты только при доказанном
рецидиве).

---

## Связи

- [Точка входа](../index.md) - карта каталога
- [Roadmap](./01-roadmap-hpta.md) - смежный исполняемый план
- [Оркестратор x3](./03-plan-audit-x3.md) - смежный план аудита
- [Контур планирования](../state/08-plan-contour.md) - фактическое состояние скила

---

## История изменений

- 2026-10-02: создан переносом planx.md (раздел 13 старого 15-plan-audit.md) без потерь
