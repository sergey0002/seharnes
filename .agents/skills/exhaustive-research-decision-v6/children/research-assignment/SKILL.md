---
name: research-assignment
description: Превращает вопросы, требования, критерии, оси покрытия и gaps в конкретные исследовательские задания с владельцем, методом, output_file и stop_condition. Использовать когда после брифа и критериев нужно раздать работу субагентам, а не поручать «исследовать всё вообще».
---

# research-assignment-router

Вход: `00-brief.md`, `task-spec.md`, `research-protocol.md`, `criteria.csv`, `feature-dictionary.csv`, `gaps.csv`, `candidates.csv`, `method-registry.md`.  
Выход: `research-assignments.csv` и запуск волн.

## 1. Единица задания

Одна строка = один проверяемый вопрос. Запрещены задания вида «изучить рынок» без границ.

```csv
assignment_id,linked_ids,objective,scope_in,scope_out,method_ids,assigned_agent,input_files,output_file,stop_condition,return_schema,max_summary_tokens,wave,status
A001,Q003;K001;G001,"дозаполнить vector_search_support по C003",["official docs","plugin repo","benchmark"],["marketing blogs"],M010;M017,feature-gap-scout,"criteria.csv;feature-dictionary.csv;gaps.csv","feature-evidence.csv","ячейка verified или обоснованный not_supported","{status,new_evidence[],unresolved[]}",2000,2,open
```

## 2. Полнота маршрутизации

Каждый из следующих объектов получает минимум одно задание:

- `Qxxx` с `blocking: yes`;
- `Rxxx` или `Kxxx` с `decision_critical: yes`;
- незакрытая ось покрытия;
- `gap_id` со статусом `open`;
- конфликт источников;
- candidate без adoption evidence;
- синтетический критерий без sensitivity.

## 3. Профили свободы

- `frontier`: можно слить несколько assignment'ов в один, если модель обоснует в `deviation-request.md` и закроет все output cells.
- `balanced`: один assignment на независимую ось.
- `regulated`: дробить и объединять нельзя; один владелец, один output_file, явный stop.

## 4. Делегирование

Субагент получает `task_id`, `input_files[]`, `output_file`, `scope_in/scope_out`, `method_ids`, `stop_condition`, `return_schema`, `max_summary_tokens`. История чата не передаётся. Полный вывод пишется в файл; родитель получает сжатый JSON. Для `frontier` лимит `max_summary_tokens` является heuristic, а не hard gate.

## 5. Stop

`ASSIGNMENT = PASS` только если нет оси-сироты, у каждого задания есть метод/владелец/output/stop, все `open` gaps назначены. Иначе `INCOMPLETE` и запрет финальной волны.

## Запрещено

- Создавать универсальные «helper» задания.
- Спавнить агентов ради количества.
- Передавать субагенту историю чата вместо путей.
- Оставлять `output_file` пустым.

## 5. Работа без нативных субагентов

Cursor регистрирует subagents только из `.cursor/agents/*.md` (или `~/.cursor/agents/`), а не из папки скилла. Пакет поэтому не требует внешней установки:

1. Для `assigned_agent` возьми `references/agents/<assigned_agent>.md` **от корня скилла** (например `references/agents/candidate-scout.md`).
2. Если одноимённый нативный subagent доступен — вызови его по имени.
3. Если нет — прочитай спецификацию и передай её содержимое как роль/system-prompt обычного `Task`/subagent вместе с `input_files`, `output_file`, `stop_condition` и `return_schema`.
4. Поля `readonly` / `is_background` из фронтматтера считай пожеланием, а не гарантией; итог всё равно проверяет `gate-verifier` через `scripts/check_gates.py`.

Опциональная нативная регистрация: см. [INSTALL.md](../../INSTALL.md) от корня пакета.
