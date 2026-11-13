#!/usr/bin/env python3
"""Batch-add AI navigation blocks and fill empty ## Связи in architecture/*.md"""
from __future__ import annotations

import re
from pathlib import Path

ARCH = Path(__file__).resolve().parents[1] / "architecture"

AI_HINTS: dict[str, tuple[str, str]] = {
    "account-session-auth.md": (
        "аккаунт, signin/signup, сессия, OAuth redirect, SessionManager, тариф в ЛК",
        "§AccountController → §SessionManager → [authorization.md](./authorization.md)",
    ),
    "admin.md": (
        "админка `/admin/`, RBAC, CRUD-контроллеры, Admin*Controller",
        "§маршруты admin → [routes.md](./routes.md) §admin; RBAC — [authorization.md](./authorization.md)",
    ),
    "author-copyrus.md": (
        "Copyrus, demand-flow, автор как правообладатель",
        "[rights-holders.md](./rights-holders.md) → [item.md](./item.md)",
    ),
    "authorization.md": (
        "логин клиента/админа, OAuth, SecLog, RBAC, RestorePassword",
        "§клиент → §админ → [account-session-auth.md](./account-session-auth.md)",
    ),
    "base-framework.md": (
        "CustomObject, DataManager, Model, Form — legacy MVC",
        "[custom-object-orm.md](./custom-object-orm.md); PSR-4 — [shared-infrastructure.md](./shared-infrastructure.md)",
    ),
    "cicd.md": (
        "Bitbucket Pipelines, деплой, migrations, CI переменные",
        "§pipeline; не читай целиком — только нужный step",
    ),
    "content-cms.md": (
        "статьи, FAQ, sitepage, CMS-контент",
        "[sitemap-seo.md](./sitemap-seo.md); роуты — [routes.md](./routes.md)",
    ),
    "cron.md": (
        "m_cron.php, m_job.php, submitPending, subscription_fee, mailing",
        "[routing-entrypoints.md](./routing-entrypoints.md) §cron",
    ),
    "deposition.md": (
        "депонирование end-to-end, CheckItem, items_limit, SOAP submit",
        "§4 лимиты → [orders.md](./orders.md) → [tariffs.md](./tariffs.md)",
    ),
    "di-container.md": (
        "SfInjector, регистрация сервисов, autowiring",
        "[sfinjector-ya-controller.md](./sfinjector-ya-controller.md); bootstrap — [routing-entrypoints.md](./routing-entrypoints.md)",
    ),
    "email.md": (
        "SendEmailService, провайдеры SES/Postbox, webhook статусов",
        "[notification-system.md](./notification-system.md); cron — [cron.md](./cron.md)",
    ),
    "events-system.md": (
        "события заказов, listeners, OrderWasCompleted",
        "[orders.md](./orders.md) → [notification-system.md](./notification-system.md)",
    ),
    "frontend.md": (
        "Vue 2, Vuex, webpack entries, legacy jQuery modules",
        "**Не читай целиком** — только нужный module/store из оглавления или file-registry",
    ),
    "index.md": (
        "первая точка входа; выбор doc по задаче",
        "[§ Дерево решений](#дерево-решений-по-типу-задачи) → [architecture.md](./architecture.md)",
    ),
    "notification-system.md": (
        "NotificationService, email/SMS триггеры от событий",
        "[events-system.md](./events-system.md) → [email.md](./email.md)",
    ),
    "online-cert-settings.md": (
        "онлайн-сертификаты, шаблоны, ONCERT",
        "[orders.md](./orders.md) service 1500 → [register-service-full.md](./register-service-full.md)",
    ),
    "orders.md": (
        "заказы, CheckItem, PayFromAccount, типы ServiceCode",
        "§CheckItem → [payments.md](./payments.md) → [deposition.md](./deposition.md)",
    ),
    "page_types.md": (
        "типы страниц, layouts, Vue vs legacy vs mixed",
        "[frontend.md](./frontend.md) §layouts; роуты — [routes.md](./routes.md)",
    ),
    "partner.md": (
        "партнёрская/реферальная программа, affCode, parentId, выплаты",
        "[payments.md](./payments.md); legacy detail — [referral-partner.md](./referral-partner.md)",
    ),
    "payments-withdraw-s3.md": (
        "вывод средств, mediateka, disk-quota, S3 в ЛК",
        "[payments.md](./payments.md) → [person-profile.md](./person-profile.md) → [s3.md](./s3.md)",
    ),
    "payments.md": (
        "ledger, YooKassa, баланс, PaymentAccountService, webhook",
        "§PaymentAccountService → [orders.md](./orders.md) §оплата",
    ),
    "person-profile.md": (
        "профиль персоны, документы, вывод средств, лимиты",
        "[payments-withdraw-s3.md](./payments-withdraw-s3.md); auth — [authorization.md](./authorization.md)",
    ),
    "promo-system.md": (
        "промокоды, ct_promo, применение при оплате",
        "[tariffs.md](./tariffs.md); регистрация — [partner.md](./partner.md)",
    ),
    "referral-partner.md": (
        "legacy ReferralPaymentService, cookie referral",
        "**Канон:** [partner.md](./partner.md)",
    ),
    "reg-object-service.md": (
        "RegObjectService, подготовка объектов к депонированию",
        "[register-service-full.md](./register-service-full.md) → [item.md](./item.md)",
    ),
    "register-oauth-legacy-root-js.md": (
        "legacy oauth.js, register.js, VK ID, jQuery auth",
        "[authorization.md](./authorization.md); modern — [account-session-auth.md](./account-session-auth.md)",
    ),
    "register-service.md": (
        "ServerService, SOAP-транспорт к реестру",
        "[server-soap.md](./server-soap.md); оркестратор — [register-service-full.md](./register-service-full.md)",
    ),
    "rights-holders.md": (
        "правообладатели, ct_rightsHolder, Author",
        "[item.md](./item.md) → [deposition.md](./deposition.md)",
    ),
    "routes.md": (
        "полный справочник m_router.php, classCode/methodCode",
        "[routing-entrypoints.md](./routing-entrypoints.md) §bootstrap; не сканировать всю таблицу — grep по classCode",
    ),
    "routing-entrypoints.md": (
        "maket.php, index.php, m_router, m_job, bootstrap",
        "§maket → [routes.md](./routes.md)",
    ),
    "security-partner-modules.md": (
        "BlackListDomain, ItemController traits, OuterPartner CPA",
        "[item.md](./item.md); admin — [admin.md](./admin.md)",
    ),
    "server-soap.md": (
        "ServerService, WSDL, SubmitRegistrationTask, retry",
        "[register-service.md](./register-service.md) → [deposition.md](./deposition.md)",
    ),
    "service-codes.md": (
        "коды услуг 700/800/…, ServiceService",
        "[orders.md](./orders.md) §типы заказов",
    ),
    "sfinjector-ya-controller.md": (
        "YaController, YaApi, интеграция DI с legacy контроллерами",
        "[di-container.md](./di-container.md)",
    ),
    "share-layout-ui.md": (
        "shared modals, SessionEndModal, TariffUiHelper, layout",
        "[frontend.md](./frontend.md) §share; session — [account-session-auth.md](./account-session-auth.md)",
    ),
    "shared-infrastructure.md": (
        "общие infra-сервисы: logger, cache, MySqlPdo",
        "PDO/транзакции — [shared-pdo-transactions.md](./shared-pdo-transactions.md)",
    ),
    "shared-pdo-transactions.md": (
        "SafePdo, DatabaseTransactionManager, ItemDraft repos",
        "[shared-infrastructure.md](./shared-infrastructure.md); ItemDraft — [item.md](./item.md)",
    ),
    "sitemap-seo.md": (
        "sitemap Job, robots, OG-теги",
        "[cron.md](./cron.md) `m_job.php`; CMS — [content-cms.md](./content-cms.md)",
    ),
    "small-modules.md": (
        "callback, reviews, FAQ helpers, мелкие контроллеры",
        "grep file-registry; доменный doc часто в [content-cms.md](./content-cms.md)",
    ),
    "tariffs.md": (
        "ct_tariff, TariffParameters, items_limit, subscription_fee",
        "§TariffParameters → [deposition.md](./deposition.md) §4",
    ),
    "task-strategies-register.md": (
        "TaskFinishStrategy, TaskFailedStrategy, webhook handlers",
        "[register-service-full.md](./register-service-full.md) → [events-system.md](./events-system.md)",
    ),
}

EXTRA_LINKS: dict[str, list[str]] = {
    "admin.md": [
        "- [Маршруты admin](./routes.md) — `admin/m_router.php`",
        "- [Авторизация](./authorization.md) — RBAC admin",
        "- [Архитектура](./architecture.md) — lifecycle, DI",
        "- [Routing entrypoints](./routing-entrypoints.md) — bootstrap admin",
    ],
    "cicd.md": [
        "- [Архитектура](./architecture.md) — структура деплоя",
        "- [Routing entrypoints](./routing-entrypoints.md) — entrypoints на сервере",
        "- [Cron](./cron.md) — post-deploy jobs",
    ],
    "frontend.md": [
        "- [Share layout UI](./share-layout-ui.md) — shared components/modals",
        "- [Routing entrypoints](./routing-entrypoints.md) — init.js transport",
        "- [Account/session](./account-session-auth.md) — auth Vue modules",
        "- [Item](./item.md) — wizard Vue/legacy",
        "- [Page types](./page_types.md) — layouts по типам страниц",
    ],
    "page_types.md": [
        "- [Frontend](./frontend.md) — webpack, Vue entry points",
        "- [Routes](./routes.md) — URL → controller",
        "- [Routing entrypoints](./routing-entrypoints.md) — layout rendering",
    ],
    "routes.md": [
        "- [Routing entrypoints](./routing-entrypoints.md) — bootstrap, privacy rules",
        "- [Architecture](./architecture.md) — HTTP lifecycle",
        "- [Admin](./admin.md) — `/admin/*` маршруты",
        "- [Account/session](./account-session-auth.md) — auth routes",
    ],
}


def parse_related(content: str) -> list[str]:
    m = re.search(r"related:\s*\[([^\]]*)\]", content)
    if not m:
        return []
    raw = m.group(1)
    items = [x.strip().strip("'\"") for x in raw.split(",") if x.strip()]
    return [x for x in items if x.endswith(".md") and x != "admin-modules.md"]


def related_to_links(related: list[str]) -> list[str]:
    lines = []
    for name in related:
        title = name.replace(".md", "").replace("-", " ")
        lines.append(f"- [{title}](./{name})")
    return lines


def make_ai_block(when: str, first: str) -> str:
    return f"\n> **AI:** {when}  \n> **Сначала:** {first}\n"


def insert_ai(content: str, ai_block: str) -> str:
    if "**AI:**" in content or "> **AI:**" in content:
        return content
    # After ## Суть block, before next ---
    m = re.search(
        r"(## Суть\s*\n)(.*?)(\n---\s*\n)",
        content,
        re.DOTALL,
    )
    if not m:
        return content
    body = m.group(2).rstrip()
    if "AI-агент:" in body and "index.md" in content:
        # index: normalize
        body = re.sub(
            r"> AI-агент:.*?(?=\n>|\n---|\Z)",
            ai_block.strip(),
            body,
            count=1,
            flags=re.DOTALL,
        )
        if "**AI:**" not in body:
            body = body.rstrip() + ai_block
    else:
        body = body + ai_block
    return content[: m.start()] + m.group(1) + body + m.group(3) + content[m.end() :]


def fill_links(content: str, name: str) -> str:
    if "(пока нет)" not in content:
        return content
    links = EXTRA_LINKS.get(name)
    if not links:
        links = related_to_links(parse_related(content))
    if not links:
        return content
    block = "\n".join(links)
    return content.replace("- (пока нет)", block, 1)


def bump_history(content: str) -> str:
    if "2026-06-12: batch-ai" in content:
        return content
    hist = re.search(r"(## История изменений\s*\n)", content)
    if hist:
        insert = "- 2026-06-12: batch-ai — блок навигации AI + связи\n"
        pos = hist.end()
        return content[:pos] + insert + content[pos:]
    return content


def bump_meta_date(content: str) -> str:
    return re.sub(
        r"updated:\s*\d{4}-\d{2}-\d{2}",
        "updated: 2026-06-12",
        content,
        count=1,
    )


def main() -> None:
    updated = []
    for path in sorted(ARCH.glob("*.md")):
        if path.name.startswith("_"):
            continue
        name = path.name
        text = path.read_text(encoding="utf-8")
        orig = text
        if name in AI_HINTS:
            when, first = AI_HINTS[name]
            text = insert_ai(text, make_ai_block(when, first))
        text = fill_links(text, name)
        if text != orig:
            text = bump_meta_date(text)
            text = bump_history(text)
            path.write_text(text, encoding="utf-8")
            updated.append(name)
    print(f"Updated {len(updated)} files:")
    for n in updated:
        print(f"  {n}")


if __name__ == "__main__":
    main()
