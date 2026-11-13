# Output compliance

Единого стандарта для гибридного research-decision dossier нет. Соответствие оценивается по семействам.

| Семейство | Артефакт v6 |
|---|---|
| PRISMA-P / OSF preregistration | `research-protocol.md`, amendments |
| PRISMA 2020 / SWiM | `sources.csv`, `claims.csv`, `contradictions.csv` |
| GRADE EtD | domain adapter для клиники |
| ISO 29148 / EARS / Volere / Gherkin | `task-spec.md`, `criteria.csv`, `verification.md` |
| ISPOR MCDA | `criteria.csv`, `decision-matrix.csv`, `synthetic-scores.csv` |
| OpenAPI / AsyncAPI / JSON Schema | domain contracts + `assets/schemas/` |
| Spec Kit / Kiro / OpenSpec / Reversa | `reuse-decision.md`, `research-assignments.csv`, deltas |
| AGENTS.md / llms.txt / Agent Skills | root `SKILL.md`, `00-state.md`, `context-budget.md` |
| Structured Outputs | `gates.json`, JSON Schema validators |
| Clean-room / characterization / Pact | `verification.md`, `parity` при rebuild-задачах |

`compliance-matrix.csv` помечает `compliant | partial | missing | n/a`. `partial` уходит в `residual_unknowns`, `missing` без owner/gap блокирует PASS.
