# QA: библиотека фрагментов теста (AcceptanceTester)

<!-- meta
type: index
status: actual
updated: 2026-09-15
related: [README.md, index.md, ../tests.md, ../harnes/doc_rules.md]
tags: [qa, e2e, fragments, codeception, page-object]
-->

---

## Суть

Каталог готовых частей теста, чтобы `prepare-task-test` собирал тест из них,
а не писал XPath и логику заново.

Частей три вида:

| Вид | Где | Что содержит |
|---|---|---|
| Page | `Support/Page/*.php` | селекторы и примитивы одного экрана |
| Step | `Support/Step/*.php` | бизнес-сценарий из нескольких Page |
| Фрагмент актора | `AcceptanceTester.php` | вход, фикстуры БД, диагностика |

Общее устройство системы: [README.md](README.md).

> **AI:** не проверяй наличие методов глазами — запусти
> `bash .doc/qa/scripts/check-tests.sh`. Он загружает все Cest и сразу
> показывает, что не резолвится. Нет нужной части → `flows/*.md` → только
> потом новый метод + строка здесь, в том же проходе.

Селекторы пишем в Page, не в актор и не в Cest задачи. Актор оставляем для
входа, фикстур и диагностики; для уже существующих экранных методов он
работает тонкой обёрткой над Page.

---

## Page-объекты

| Page | Экран | Ключевые методы |
|---|---|---|
| `Page\WizardPage` | `/item/start`, многошаговая форма депонирования | `open($strategy)`, `fillStep2()`, `goToStep()`, `fillFizikSubject()`, `checkCopyrights()`, `saveDraft()`, `grabCurrentStep()`, `seeNameError()`, `dontSeeStrategyValidationError()` |
| `Page\SigninPage` | `/account/signin` | `open()`, `seeLoginFormContract()`, `seeRequiredStars()`, `seeVueNotHtml5Required()`, `seeEmptySubmitBlocked()` |
| `Page\SignupPage` | `/account/signup` | `open()`, `seeSignupFormContract()`, `seeRequiredStars()`, `seeOptionalFieldsHaveNoStar()`, `seeEmptySubmitBlocked()`, `touchEmptyFieldsAndSeeVueErrors()` |
| `Page\OauthIdAccessPage` | signin/signup OAuth-кнопки + guard | `openSignin()`, `openSignup()`, `seeSocialButton()`, `seeGetUrlDisabled()`, `seeRegisterDisabled()`, `seeVkIdConfigEnabled()` (CT-2231) |
| `Page\AccountGuestFormPage` | база signup/signin | `seeRequiredStar()`, XHR-зонд, фильтр шума капчи |
| `Page\OrderCheckPage` | `/order/check`, заказ проверки качества | `open()`, `seedSubjects()`, `seeWarning()`, `dontSeeWarning()`, `seeWarningContains($uin)` |
| `Page\BookingCalendarPage` | календарь слотов на make | `waitReady()`, `seeHasSlots()`, `seeEmptyMessage()`, `seeCurrentCaption()`, `grabSelectedStart()`, `seeFirstSlotSelectedByDefault()` |
| `Page\ConsultationMakePage` | `/order/consultation` | `open()`, `setType()`, `seedQuestion()`, `acceptPrivacy()`, `seeSubmitDisabled()`, `submit()`, `waitRedirectToOrderView()` |
| `Page\RegistrationHelpMakePage` | `/order/registration_help` | `open()`, `selectDraft()`, `acceptPrivacy()`, `submit()` |
| `Page\OrderViewBookingPage` | `/order/view/{id}` бронь/оплата | `seeBookingFields()`, `seeDataLoss()`, `confirmPayFromBalance()`, `seeConflictModal()` |
| `Page\AdminOrderBookingPage` | `/admin/m_order.php` save-booking / datatable / details (CT-2548 Герман) | `open()`, `openPending()`, `grabOrderFromDatatable()`, `seeBookingFilledInDatatableRow()`, `grabDetailsHtml()`, `seeBookingInDetailsHtml()`, `seeDataLossInDetailsHtml()`, `saveDateTime()` |
| `Page\OrderNeighborPage` | `/order/pksr` без календаря брони | `openPksr()` |
| `Page\OrderMainPage` | `/order/main`, групповая оплата | `open()` ждёт `init`; `seeUnpaidCountInHeader()`, `seeBannerSum()`, `seeModalPayable()`, `grabUnpaidState()`, `seePayBannerEnabled()`, `openPayModal()`, `acceptAgreement()`, `clickModalPay()`, `clickModalCancel()`, `waitConfirmFromAccount()`, `confirmPayYes()`, `confirmPayNo()`, `waitOneClick()`, `seeOneClickPriceNotZero()`, `applyStatusFilterAll()`, `seeSkipLabel()` |
| `Page\OrderViewPage` | `/order/view/{id}` карточка заказа | `open($id)`, `waitStatus()`, `seeCommentContains()`, `dontSeeCancelButton()`, `postCancel()`, `requestCerts()` |
| `Page\OrderMainPage` | `/order/main` список заказов | `open()`, `seeStatusInFilter()`, `filterByStatusId()`, `seeOrderInTable()` |
| `Page\AdminOrdersPage` | `/admin/m_order.php` | `openAll()`, `openPending()`, `grabStatusesJson($pending)` |
| `Page\AdminDbLogPage` | `/admin/m_dblog.php` | `openWithoutTimes()`, `openErrorsAndNotices()`, `seeDescription()` |
| `Page\AccountRemindRestorePage` | `/account/remind`, `/account/remind/{hash}` | `openRemind()`, `openRestore($hash)`, `seeRemindSpinner()`, `mockForgotThenPollSuccess()`, `seeLetterSentStayingOnRemind()`, `seeUnknownEmailError()`, `seedRestoreHash()` |
| `Page\AccountEditPage` | `/account/edit` сообщения и ОИС | `openMessagesAccordion()`, `openOisAccordion()`, `changePassword()`, `seeUnifiedPayConfirm()`, `confirmPay()`, `seeNoServiceError()`, XHR probe (CT-2605, CT-2603, CT-2477) |
| `Page\AdminTariffListPage` | `/admin/m_tariff.php`, удаление тарифа | `open()`, `deleteTariff($id)`, `waitForErrorToast()`, `waitTariffGoneFromList()`, `seeDeleteButton()`, `dontSeeDeleteButton()` |
| `Page\AdminTariffEditPage` | `/admin/m_router.php?q=tariffs/edit/{id}` | вкладка SFEE: скидка 2429 + альтернатива 2427 (`openSfeeTab`, `selectAlternative`, `saveViaVue`) |
| `Page\TariffListPage` | `/tariffs`, `/`, `/tariffs/showall` | `open()`, `openHome()`, `openShowall()`, restricted badge/tooltip, `window.tariffs` labels, `isOnShowcase` ids, showall status, POST `/tariff/all` |
| `Page\TariffViewPage` | `/tariffs/view/{id}` | `seeAvailableProfilesRow()`, archive/connect (CT-2511) |
| `Page\BasePage` | база | `self::test($name)`, `self::testIn()`, поиск Vue-компонента по тегу |
| `Page\ProfileEditPage` | `/profile/edit` webpack | `open()`, dirty/unload (CT-2607), `seedClientAsIpWithLastname`, `replaceLastnameViaDomInput` (CT-2608) |
| `Page\AdminClientProfilePage` | `/admin/m_router.php?q=client/edit/{id}`, логин | `open($id)`, `openGeneralParams()`, `setLogin()`, `save()`, `seeAccountSavedToast()`, `seeExistingEmailError()` |
| `Page\SigninPage` | `/account/signin` | `open()`, `loginWithPassword()`, `loginRemembering()`, `submitCredentials()`, `seeLoginRejected()`, `seeCabinet()`, `seeDesktopIdLayout()`, `seeMobileIdMenuToggle()` (CT-2477, CT-2252) |
| `Page\TariffFullListPage` | `/tariffs/showall` и ссылка с `/tariffs` | `open()`, `seeHeadingAndColumns()`, `seeRow()`, `seeBadge()`, `seeFeeYes/No()`, `openVitrine()`, `clickVitrineFullListLink()`, `openLegacyAllAndDontSeeFullList()` |
| `Page\TariffShowcasePage` | `/`, `/tariffs`, `/tariffs/view/{id}`, `/tariffs/change` | `openHome()`, `openIndex()`, `openView()`, `openChange()`, `seeStrikeOldAndCurrentPercent()`, `seeMainpageCircleDiscount()`, `dontSeeDiscountMarkup()`, computed CSS |
| `Page\TariffViewPage` | `/tariffs/view/{id}` | `open($id)`, `seeArchiveLabel()`, `dontSeeConnectButton()`, `seeConnectButton()` (CT-2511) |
| `Page\TariffChangePage` | `/tariffs/change?id=` | CT-2511 redirect/modal; CT-2379 `waitReady`, `clickConnect`, preview, Да/Нет, success recalc |
| `Page\OrderRemovePage` | `/order/remove`, заказ удаления ОИС (2030) | `open($rid)`, `openFromTechnicalServicesTile()`, `seeTitle()`, `seePinFieldIsText()`, `seeTaskLiterals()`, `seeSubmitDisabled()`, `seedSubjectAndConsent()`, `clickSubmit()`, `postMakeRemove()` |
| `Page\OrderViewPage` | `/order/view/{id}` | `open($id)`, статусы 2077, `seePayButton`, `grabPaymentSum`, `acceptPrivacyAndOpenPayConfirm`, `postCancel` |
| `Page\ItemViewPage` | `/item/view/{UIN}` | `open($uin)`, `grabFirstRegistrationUin()`, `pickAdminClientId()`, `seeAdminSoapJsonToggle()`, `expandSoapJson()`, `grabSoapJsonPayload()`, `seeSoapJsonMatchesUin()`, `seeNeighborAdminItemControls()` |

Текущий шаг wizard берётся из Vuex (`storeVue.state.Item.wizard.step`), а не
из DOM: пройденные шаги остаются в разметке под `v-show`, проверка по DOM даёт
ложный результат (см. deposition.md (`../architecture/deposition.md`; missing in kit) §10).

## Step-объекты

| Step | Сценарии |
|---|---|
| `Step\DepositionSteps` | `fillMinimalUpToRights()`, `createDraft()`, `assertStep2RequiresName()`, `assertStrategyOpens()` |
| `Step\BookingSteps` | `createSpokenConsultation()`, `occupyStaffInterval()`, `ensureSecondStaffForType()` |
| `Step\AdminClientProfileSteps` | `openAsAdmin()`, `changeLoginAndSave()` (CT-2597) |
| `Step\AuthRequiredFieldsSteps` | `assertSignupRequiredMarkers()`, `assertSigninRequiredMarkers()`, `assertSignupSubmitBlocked()`, `assertSigninSubmitBlocked()` |

---

## Фрагменты актора

| Фрагмент | Метод | Что делает | Использует / связано |
|---|---|---|---|
| Вход тест-клиентом (id=1, фиксированный) | `loginAsClient()` | Форма `/account/signin`, кэш через session snapshot `login` | [account-signin.md](flows/account-signin.md) |
| Фикстура тест-клиента | `haveInDbDefaultClient()` | upsert `ct_country`+`ct_tariff`+`ct_tariff_uac_parameters`+`ct_client` (id=1) | вызывается из `loginAsClient()`; на dev-БД записи уже есть - не `haveInDatabase` вслепую |
| Вход админом | `loginAsAdmin()` | upsert `ct_user`/roles + `dev-login.php?as=admin` + `/admin/` | SmartCaptcha только на POST формы; см. [browser-setup.md П-7](browser-setup.md#п-7-smartcaptcha-на-входе-в-админку) |
| Вход клиентом без формы | `devLoginAsClient(int $clientId)` | `dev-login.php?as=client&id=N`, тот же `startClientSession()` что и обычный вход | быстрее `loginAsClient()`, когда сам вход не предмет теста; только dev/test стенд |
| Вход админом без формы | `devLoginAsAdmin($login, $pass)` | upsert админа + `dev-login.php?as=admin` | только dev/test стенд |
| Фикстура админа | `haveInDbDefaultAdmin($login, $pass)` | upsert `ct_user`, `ct_right`, `ct_role`, связки | вынесено из `loginAsAdmin()`, чтобы dev-вход тоже гарантировал пользователя |
| Тариф для теста | `haveInDbTariff(int $id, array $overrides)` | upsert `ct_tariff` + `ct_tariff_uac_parameters` | [tariff-delete.md](flows/tariff-delete.md), CT-2428, [tariff-showcase-discount.md](flows/tariff-showcase-discount.md), CT-2429 |
| Промо для теста | `haveInDbPromo(int $tariffId, array $overrides)` | insert `ct_promo` | CT-2428 |
| Удаление тарифа в UI | `deleteTariffViaAdmin(int $tariffId)` | обёртка над `adminTariffListPage()->deleteTariff()` | CT-2428, [tariff-delete.md](flows/tariff-delete.md) |
| Page списка тарифов | `adminTariffListPage()` | делегат в `Page\AdminTariffListPage` | CT-2428 |
| Page профиля клиента в админке | `adminClientProfilePage()` | делегат в `Page\AdminClientProfilePage` | CT-2597, [admin-client-login.md](flows/admin-client-login.md) |
| Page входа клиента | `signinPage()` | делегат в `Page\SigninPage`, `loginRemembering()` (CT-2477) | [account-signin.md](flows/account-signin.md) |
| Модалка истечения сессии | `sessionEndModalPage()` | делегат в `Page\SessionEndModalPage` | CT-2477 |
| Последняя запись ct_sec_log | `grabLatestSecLogData($action)` | SELECT data ORDER BY id DESC | CT-2477 |
| Page регистрации | `signupPage()` | делегат в `Page\SignupPage` | CT-2591 |
| Page OAuth ID флаги | `oauthIdAccessPage()` | делегат в `Page\OauthIdAccessPage` | CT-2231 |
| Page wizard | `wizardPage()` | делегат в `Page\WizardPage` | [item-draft.md](flows/item-draft.md) |
| Page списка заказов | `orderMainPage()` | делегат в `Page\OrderMainPage` | CT-2061, CT-2077 |
| Page правки тарифа в админке | `adminTariffEditPage()` | делегат в `Page\AdminTariffEditPage` | CT-2427, CT-2429 |
| Page полного списка тарифов | `tariffFullListPage()` | делегат в `Page\TariffFullListPage` | CT-2520 |
| Page витрины тарифов | `tariffListPage()` | делегат в `Page\TariffListPage` | CT-2467, [tariff-showcase-markers.md](flows/tariff-showcase-markers.md) |
| Вход под произвольным `clientId` через админку | `loginAsClientById(int $clientId)` | `loginAsAdmin()` → синхронный XHR на `client/login-by-client` → `/account/edit` | admin.md §3 (`../architecture/admin.md#3-авторизация-администратора`; missing in kit), см. [`.doc/harnes/tests.md`](../harnes/tests.md) §2. Клиент с этим id должен уже существовать в БД — метод не создаёт клиента |
| Чекпойнт качества (скрин+консоль+DOM-дельта+сообщения) | `checkpoint(string $label)` | `makeScreenshot()`, ошибки консоли, дельта `grabPageSource()` по строкам, видимые модалки и `.toasted`; пишет строку в `_output/checkpoints.jsonl` | вызывать после каждого значимого шага, не только в конце. Закрывает категории 6, 8, 9 чек-листа [`tests.md`](../harnes/tests.md) §7. Сам тест не валит |
| Инициализация перехвата консоли | `initConsoleCapture()` | Один раз за сессию ставит `console.error`/`window.onerror`/`unhandledrejection` | вызывается из `checkpoint()`, идемпотентен |
| Чтение накопленных ошибок консоли | `grabConsoleErrors(): array` | `return window.__testConsoleErrors \|\| []` | используется в `checkpoint()` и напрямую |
| Сброс накопленных ошибок | `resetConsoleErrors()` | обнуляет список | когда шаг заведомо шумит и это ожидаемо |
| Строгая проверка консоли (падает тест) | `seeNoConsoleErrors()` | бросает assertion при непустом списке | на шагах, где консоль обязана быть чистой |
| Видимые сообщения страницы | `grabPageMessages(): array` | `errorModal`, `modals`, `toasted` | детект по заголовку `h2.modal-header__title`, см. П-6 |
| Строгая проверка модалки ошибки | `dontSeeErrorModal()` | падает, если видна модалка с заголовком "Ошибка…" | парная к `seeNoConsoleErrors()` |
| Same-origin GET | `grabSameOriginGet($path)` | синхронный XHR со страницы стенда | CT-2354 `refund-smoke.php` |
| Черновик через wizard | `Step\DepositionSteps::createDraft($strategy)` | Шаги 2-4 + сохранение, с `checkpoint()` на каждом шаге | [item-draft.md](flows/item-draft.md), заменяет копипасту из `ItemDraftCest` |
| Фикстура готового черновика (id=1, clientId=1) | `haveInDbItemDraft()` | Прямая вставка в `ct_item`+`ct_author`+`ct_rightsHolder` (аналог `saveFullDraft`, но без UI — для тестов, где сам wizard не предмет проверки) | используется в тесте прав доступа `ClientCest::clientCannotSeeAnotherClientsDraft` |
| Фикстура второго клиента (id=2) | `haveInDbSecondClient()` | `ct_client` (id=2), переиспользует `ct_country`/`ct_tariff` из `haveInDbDefaultClient()` — вызывать после него | тесты прав доступа (категория 11), см. [item-draft.md](flows/item-draft.md) |
| Заказ проверки качества — открыть форму | `amOnOrderCheckPage()` → `Page\OrderCheckPage::open()` | `/order/check`, ждёт `.order-cert` и готовность Vue | [order-quality-check.md](flows/order-quality-check.md), CT-2236 |
| Заказ проверки качества — подставить ОИС с флагами обложки/образцов | `seedOrderCheckQualitySubjects(array $items)` | Инъекция в Vue `order-subject-list2` без SOAP: сперва `qualityFlags`, потом `values`, иначе watch уйдёт в реальный XHR | CT-2236 |
| Предупреждение качества видно / скрыто | `seeOrderQualityWarning()` / `dontSeeOrderQualityWarning()` / `seeOrderQualityWarningContains($uin)` | селектор по классу обёртки `.order-check-quality-warning--desktop`, см. П-7 | CT-2236 |
| Заказ ПКСР/выписка/комплект - открыть форму | `amOnOrderPrintForm($url, $title)` | GET URL, заголовок, `.order-cert-country`, getter `allGeographic` | [order-print-country.md](flows/order-print-country.md), CT-2606 |
| Список стран заказа без спец-кодов | `seeOrderCountryListWithoutSpecialCodes()` | getter без NONE/NOT_EXIST, меню vue-select без спец-имён | CT-2606 |
| Поиск спец-имени в стране заказа | `seeOrderCountrySearchRejectsStateless()` | "Без гражданства" -> "Ничего не найдено" | CT-2606 |
| Матрица флагов писем учётка/тариф | `seedClientMessageFlags(...)` | UPDATE `ct_client` + `ct_tariff_uac_parameters` | [account-messages.md](flows/account-messages.md), CT-2605 |
| Открыть блок сообщений в учётке | `amOnAccountEditMessages()` | `/account/edit` + spoiler "Настройка сообщений" | CT-2605 |
| Состояние чекбокса сообщений | `seeAccountMessageCheckbox($label, $checked, $disabled)` | label.checkbox__item + input checked/disabled | CT-2605 |
| Клик покупки опции сообщений | `openAccountMessagePurchase($label)` | click checkbox | CT-2605 |
| Модалка оплаты сообщений | `seeAccountMessagePayConfirm()` / `cancelAccountMessagePayConfirm()` | Нет / Оплатить (#2603) | CT-2605 |
| Аккордеон ОИС в учётке | `amOnAccountEditOisParams()` | регресс shared checkbox | CT-2605 |
| Page учётки | `accountEditPage()` | делегат в `Page\AccountEditPage` | CT-2603, CT-2605 |
| Флаги ОИС учётки | `seedClientOisFlags($pin, $closed, $pseud)` | UPDATE `ct_client` + UAC 0 | CT-2603 |
| Услуга тарифа active | `setTariffServiceActive($tariffId, $code, $active)` | `ct_tariff2Service.active` (нет услуги при 0) | CT-2603, П-16 |
| Page пополнения | `paymentsMainPage()` | делегат в `Page\PaymentsMainPage` | CT-2602, CT-2609, [payments-replenishment.md](flows/payments-replenishment.md) |
| DEFAULT kurs канала | `grabPaymentChannelKursColumnDefault()` | SHOW COLUMNS `ct_paymentChannel.kurs` | CT-2602 stage2 |
| Страница удаления ОИС | `orderRemovePage()` | Page `/order/remove` | [order-remove.md](flows/order-remove.md), CT-2070 |
| Карточка заказа | `orderViewPage()` | Page `/order/view/{id}` | CT-2070, CT-2354 `clickCancel` / `seeStatusCancelled` |
| Step депонирования | `depositionSteps()` | делегат в `Step\DepositionSteps` | [item-draft.md](flows/item-draft.md) |
| Step обязательных полей auth | `authRequiredFieldsSteps()` | делегат в `Step\AuthRequiredFieldsSteps` | CT-2591 |
| Step логина в админке | `adminClientProfileSteps()` | делегат в `Step\AdminClientProfileSteps` | CT-2597 |
| Step бронирования | `bookingSteps()` | делегат в `Step\BookingSteps` | CT-2548 |
| Page remind/restore | `accountRemindRestorePage()` | делегат в `Page\AccountRemindRestorePage` | CT-2601 |
| Page логов админки | `adminDbLogPage()` | делегат в `Page\AdminDbLogPage` | CT-2077 |
| Page сохранения брони в админке | `adminOrderBookingPage()` | делегат в `Page\AdminOrderBookingPage` (datatable/details/save-booking, CT-2548 Герман) | CT-2548 |
| Page списка заказов в админке | `adminOrdersPage()` | делегат в `Page\AdminOrdersPage` | CT-2077, CT-2354 `changeStatusJs` / `seeJsonResultTrue` |
| Page календаря слотов | `bookingCalendarPage()` | делегат в `Page\BookingCalendarPage` | CT-2548 |
| Page консультации | `consultationMakePage()` | делегат в `Page\ConsultationMakePage` | CT-2548 |
| Page карточки UIN | `itemViewPage()` | делегат в `Page\ItemViewPage` | CT-2596 |
| Page соседнего заказа без календаря | `orderNeighborPage()` | делегат в `Page\OrderNeighborPage` | CT-2548 |
| Page брони на карточке заказа | `orderViewBookingPage()` | делегат в `Page\OrderViewBookingPage` | CT-2548 |
| Page помощи с регистрацией | `registrationHelpMakePage()` | делегат в `Page\RegistrationHelpMakePage` | CT-2548 |
| Page смены тарифа | `tariffChangePage()` | делегат в `Page\TariffChangePage` | CT-2379, CT-2511 |
| Page витрины скидок | `tariffShowcasePage()` | делегат в `Page\TariffShowcasePage` | CT-2429 |
| Page карточки тарифа | `tariffViewPage()` | делегат в `Page\TariffViewPage` | CT-2511, CT-2467 |

---

## Известные проблемы и ограничения

### П-1: `ItemDraftCest` ещё не переведён на `Step\DepositionSteps` (частично закрыт)

`Page\WizardPage` и `Step\DepositionSteps` созданы, но сам `ItemDraftCest`
пока держит заполнение формы в теле Cest-метода, включая хрупкие CSS
(`#step-4_rafi-8 .ui-selectmenu-button...`) и `$I->wait(5)` вместо
`waitForElement`. Перевести при следующей правке этого теста: селекторы
уходят в `WizardPage`, шаги в `DepositionSteps`.

### П-2: `checkpoint()` — перехват консоли ставится через тест, не через приложение

В стеке есть готовый JS-обработчик `scripts/errorHandler.js` (`JSerrHandler`),
но его подключение (`window.onerror = JSerrHandler`) закомментировано —
приложение сейчас не логирует JS-ошибки само. `initConsoleCapture()` ставит
свой независимый перехватчик через `executeJS`, не трогая прикладной код.
Если `errorHandler.js` включат в проекте — перехватчики не конфликтуют
(оба независимо слушают `window.onerror`), но дублирование стоит иметь в виду.

### П-3: `.toasted` — CSS-класс, а не `data-test` (осознанное исключение конвенции)

Все всплывающие сообщения сайта (заказы, профиль, депонирование, оплата —
30+ мест через `$toasted.show(...)`) идут через вендорную библиотеку
`vue-toasted` (`scripts/plugins/vue-toasted/toasted.js`, бандл
`vue_plugins2` в `webpack.config.js`), а не через `templates/include/bell.tpl`
(этот файл пустой и нигде не `{include}`-ится — мёртвый код). Библиотека
поддерживает только добавление CSS-класса к тосту (`options.className`), не
произвольных атрибутов — добавлять `data-test` пришлось бы патчить
минифицированный вендорный бандл (`vue-toasted.min.js`, который по
`webpack.config.js` грузится в паре с неминифицированным `toasted.js` в один
entry — неясно, чей код реально выигрывает в runtime без пересборки и
проверки в браузере). Решение: **не патчить вендорную библиотеку**, использовать
уже существующий глобальный класс `.toasted` (стоит на каждом тосте всегда,
`toasted.js:741`) как стабильный селектор — это документированное исключение
из правила «только `data-test`» (см. [index.md](index.md#конвенция-селекторов-data-test)).

### П-4: `loginAsAdmin` больше не использует POST-форму и session snapshot

Раньше: fill `/admin/` + snapshot `admin-login`. Сейчас (CT-2428): upsert user/rights
в БД + `dev-login.php?as=admin`, потому что POST требует Yandex SmartCaptcha
(`admin/index.php`). Session snapshot для админа убран - каждый тест получает
свежие cookie через dev-login.

---

### П-5: таблица фрагментов опережала PHP (закрыто 2026-09-15)

Долгое время строки `checkpoint`, `initConsoleCapture`, `grabConsoleErrors`,
`seeNoConsoleErrors`, `loginAsClientById`, `haveInDbSecondClient`,
`devLoginAsClient`, `devLoginAsAdmin`, `amOnOrderCheckPage`,
`seedOrderCheckQualitySubjects`, `seeOrderQualityWarning*` были только в
документации: методов в `AcceptanceTester.php` не существовало, и шесть Cest
падали на fatal error. Плюс модуль `Asserts` не был включён в suite, из-за
чего `$I->fail()` и `assertSame()` тоже не работали.

Сейчас всё это реализовано, модуль включён. Проверка на будущее —
`check-tests.sh`, он загружает все Cest и показывает нерезолвящиеся вызовы
без запуска браузера.

### П-6: модалки различаются заголовком, а не `data-test`

Все модалки проекта рендерит общий Vue-компонент `modal`
(`scripts/plugins/vue/vue.modal.js`) с заголовком в `h2.modal-header__title`.
Отдельного `data-test` у них нет. Модалка ошибки отличается только текстом
заголовка: «Ошибка» (`share/ui/error-modal.tpl`), «Ошибка сети» и
«Ошибка сервера» (`session-end-modal`). «Сообщение» — это подтверждение,
не ошибка. Поэтому `grabPageMessages()` матчит заголовок по `/^Ошибк/`.

### П-7: у предупреждения качества нет `data-test`

`order-check-quality-warning.tpl` рендерит `<span class="red">` внутри
обёрток `.order-check-quality-warning--desktop` / `--mobile`. Селектор идёт
по классу обёртки. Шаблон ради теста не правим.

### П-8: `item-form-step2__name-error` не существует

[item-draft.md](flows/item-draft.md) ссылался на `data-test="item-form-step2__name-error"`,
которого в `step2.tpl` нет. Ошибки валидации рендерятся как
`<p class="reg-author-form__error-text">` внутри `label` поля.
`WizardPage::seeFieldError()` ищет именно так.

---

## Связи

- [README.md](README.md) — устройство тестовой системы, скрипты, гейты
- [`.doc/qa/index.md`](index.md) — реестр флоу и конвенция `data-test`, откуда пришло исключение П-3
- [`.doc/harnes/tests.md`](../harnes/tests.md) — канон: чек-лист §7, стандарт отчёта §8
- `.doc/codeception/tests/Support/AcceptanceTester.php` — фрагменты актора
- `.doc/codeception/tests/Support/Page/`, `Step/` — селекторы и бизнес-шаги

---

## История изменений

- 2026-09-30: `Page\PaymentsMainPage` для CT-2556: `waitChannelPresent`, `clickChannelHeader`, `postPreviewRaw` (Vue-списки, клик по заголовку, декодированный wmerror)

- 2026-09-15: восстановлены делегаты Page/Step в акторе после коллизии (все существующие Page кроме BasePage + все Step)
- 2026-09-15: CT-2603 `AccountEditPage` unified confirm, `seedClientOisFlags`, `setTariffServiceActive`
- 2026-09-15: CT-2077: `OrderViewPage` cancel/ZIP, `OrderMainPage` фильтр статусов, `AdminOrdersPage` pending без 9, `AdminDbLogPage` refund
- 2026-09-15: `Page\ItemViewPage` для CT-2596 (JSON SOAP на карточке UIN)
- 2026-09-15: `OrderRemovePage` / `OrderViewPage` и делегаты актора для CT-2070
- 2026-09-16: `grabPaymentChannelKursColumnDefault()` для CT-2602 stage2
- 2026-09-15: `Page\PaymentsMainPage` + `paymentsMainPage()` для CT-2602
- 2026-09-15: `Page\TariffViewPage`, `TariffChangePage`, `TariffListPage` для CT-2511
- 2026-09-15: `TariffChangePage` preview/Да/Нет и `OrderViewPage::grabPaymentSum` для CT-2379
- 2026-09-15: `Page\AdminTariffEditPage` альтернатива CT-2427 (тот же экран, что скидка 2429)
- 2026-09-15: `Page\AccountRemindRestorePage` для CT-2601 (remind/restore UX)
- 2026-09-15: `TariffShowcasePage` + `AdminTariffEditPage` для скидки витрины CT-2429
- 2026-09-15: `OrderRemovePage` / `OrderViewPage` и делегаты актора для CT-2070
- 2026-09-15: `Page\TariffFullListPage` для CT-2520 (`/tariffs/showall`)
- 2026-09-15: Page signup/signin и Step `AuthRequiredFieldsSteps` (CT-2591)

- 2026-09-15: Page/Step бронирования CT-2548 (`BookingCalendarPage`, `BookingSteps`)
- 2026-09-15: добавлены слои Page и Step; реализованы фрагменты, которые
  раньше были только в таблице (П-5 закрыт); включён модуль `Asserts`;
  новые П-6, П-7, П-8 по фактической разметке

- 2026-09-14: фрагменты блока сообщений учётки CT-2605 (`seedClientMessageFlags`,
  `amOnAccountEditMessages`, `seeAccountMessageCheckbox`, purchase/cancel, OIS accordion)
- 2026-09-14: фрагменты списка стран заказа CT-2606 (`amOnOrderPrintForm`,
  `seeOrderCountryListWithoutSpecialCodes`, `seeOrderCountrySearchRejectsStateless`)
- 2026-08-12: `loginAsAdmin` через dev-login; upsert в `haveInDbDefaultClient`;
  фрагменты tariff delete (CT-2428); П-4
- 2026-07-09: файл создан по плану `.doc/harnes/tests.md`; задокументированы фрагменты
  `loginAsAdmin`/`haveInDbDefaultAdmin`/`loginAsClientById`/`checkpoint`/
  `initConsoleCapture`/`grabConsoleErrors`/`seeNoConsoleErrors`, найдено что
  `bell.tpl` мёртвый и реальный механизм сообщений — `vue-toasted` (П-3)
- 2026-07-09: добавлены `haveInDbItemDraft()`/`haveInDbSecondClient()` — фикстуры
  для теста прав доступа `ClientCest::clientCannotSeeAnotherClientsDraft`
