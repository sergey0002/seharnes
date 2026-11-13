# Comment Triage (gototask post-apply)

После успешного `gototask` apply, если в `task.md` есть ## Comments с непустыми записями моложе 7 дней, выполнить triage последнего комментария.

## Триггер

Автоматический вызов из gototask шага 6, если свежие комментарии найдены.

## Workflow

1. **Прочитать последний комментарий** из `task.md` (секция ## Comments, самая свежая запись).
2. **Классифицировать** по одной из категорий:
   - `QUESTION` - вопрос, требующий ответа или уточнения
   - `BUG` - инцидент, описание воспроизведения или свидетельство ошибки
   - `REQUIREMENT` - новое требование, дополнительный AC, изменение scope
   - `DECISION` - утверждённое решение, подтверждение варианта
   - `AMBIGUOUS` - неоднозначный или неполный контекст
3. **Проверить evidence** (обязательно для BUG/REQUIREMENT):
   - `diff.md` задачи: есть ли упомянутые файлы/компоненты
   - код в репо: совпадает ли с описанием в комментарии
   - `plan.md`: есть ли это в AC или R/S
4. **Вывести triage-блок**:
   ```
   === Comment Triage ===
   Type: {QUESTION|BUG|REQUIREMENT|DECISION|AMBIGUOUS}
   Date: {дата комментария}
   Author: {автор}
   Text: {краткая цитата, до 200 символов}
   
   Evidence check:
   - diff.md: {found|missing|N/A}
   - code match: {yes|no|not checked}
   - plan coverage: {AC-ID|R-ID|none|N/A}
   
   Action:
   {конкретное предложение: "ответить в Jira", "добавить в plan.md как R-{N+1}", "уже покрыто AC-{ID}", "требует уточнения у автора"}
   
   Next command: {prepare-plan|task-doc|"ответ в Jira"|none}
   ```
5. **Не запускать** следующую команду автоматически - только предложить.

## Ограничения

- Не выполнять, если комментариев нет или последний старше 7 дней.
- Не commit в plan.md или task.md без явного запроса пользователя.
- Не отправлять комментарии в Jira через MCP без подтверждения.
- Evidence check для BUG/REQUIREMENT обязателен, для остальных опционален.

## Связи

- [gototask SKILL.md](../SKILL.md) - шаг 6
- [prepare-plan SKILL.md](../../prepare-plan/SKILL.md) - если требуется обновить план
- [task-doc SKILL.md](../../task-doc/SKILL.md) - если требуется зафиксировать решение
