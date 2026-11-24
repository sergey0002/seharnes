# Инструкция типа doc

## Когда применять
Применяй для документации продукта. `doc` — текущий generic type документационного
домена внутри `todone`, а не второй runtime и не отдельная обязательная очередь
`todoc`.

## Цель
Документировать только реализованное или явно помеченное как declared/proposed,
сохранить связь с кодом, задачей, тестами и решением. Не превращать свободное
объяснение модели в подтверждённый факт.

## Как работать
Прочитай bounded task/context packet и только затронутые документы/refs. Обнови
affected modules, claims/provenance и пользовательскую документацию, проверь
схему и render, оставь указатели. Не меняй код вместо описания. Если старый
документ конфликтует с code/test evidence, сохрани conflict/unknown и вынеси
proposal или вопрос, а не переписывай историю молча.

## Явный intent
Команда или chat-intent `задокументируй` означает: построить bounded DOC_PACKET,
предложить/create revision и вернуть diff/preview до policy или human approval.
При активной задаче используй её refs; без задачи допускается lightweight
`source.system=chat` capture record. Обычная беседа без этого intent не создаёт
документ автоматически.

## Запасной путь
Если будущий docs-store/catalog/resolver недоступен, правь локальные Markdown и
machine sidecars только в разрешённом workspace и зафиксируй команду проверки
схемы/render. Отсутствие optional store не маскируй под полный успех.

## Результат
Верни JSON-compatible report: `docs_changed`, `doc_keys`, `claims_changed`,
`source_refs`, `render_check`, `stale_check`, `verdict`, `unknowns` и `next_action`.
Текущий v0.7 writer может вернуть только уже объявленные поля; дополнительные
поля являются целевым DOC-1 return contract до реализации.
