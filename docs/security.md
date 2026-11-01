# Безопасность

Пользовательский запрос: JWT → Auth.verify → действующая Redis-сессия → актуальные роли Identity → Actor → ApplicationFacade. Logout удаляет sid. Пароль хранится как PBKDF2-HMAC-SHA256 со случайной солью.

Публичная регистрация создаёт PENDING. Эта роль не получает финансовую аналитику, расчёты, импорты и отчёты. Роль назначает оператор командой `python -m app.scripts.assign_role EMAIL ROLE` в доверенной среде. Публичного назначения ролей нет.

| Операция | ANALYST | PRODUCTION_ACCOUNTANT | FINANCE_ACCOUNTANT | MANAGER | ADMIN |
|---|---|---|---|---|---|
| products | Да | Да | Да | Да | Да |
| profitability, summary, costBreakdown, allocations | Да | Нет | Нет | Да | Да |
| importRuns | Оба контура | ERP/MES | FINANCE | Нет | Оба контура |
| startProductionImport | Нет | Да | Нет | Нет | Да |
| startFinancialImport | Нет | Нет | Да | Нет | Да |
| retryImport | Нет | ERP/MES | FINANCE | Нет | Оба контура |
| resolveExternalMapping | Нет | Да | Да | Нет | Да |
| calculateCost / calculateProfitability | Да | Нет | Нет | Нет | Да |
| exportReport | Свой отчёт | Нет | Нет | Свой отчёт | Свой отчёт |

Для importRuns без source выбираются только разрешённые направления; явно запрещённый source даёт AuthorizationError. requested_by не принимается от клиента: фасад определяет его из Actor. SavedReport.user_id проверяется в Reporting до создания REPORT_EXPORT. Фасад также защищает чтение чужой выгрузки.

Внутренний gRPC использует подписанный служебный JWT: iss=profitability-internal, aud=internal-rpc, role=INTERNAL_SERVICE, sub, iat и exp. Только gateway может инициировать изменяющие методы; сервисные клиенты выполняют чтение по своей служебной идентичности. User JWT не принимается вместо service JWT. Порты gRPC закрыты для хоста в Compose. INTERNAL_JWT_SECRET — отдельный ключ из окружения, обязательный для standalone server; тестовый процесс использует общий эфемерный ключ.
