# Сверка замечаний лабораторных

| Лаба | Замечание | Исправление |
|---|---|---|
| 1 | Источник плановых показателей | Master Data PLANNED_COST; снимок плана и отклонение в калькуляции |
| 1 | Исходные финансовые факты | FINANCIAL_ENTRY OVERHEAD/CORRECTION; OVERHEAD_ALLOCATION принадлежит Costing |
| 1 | Владелец сопоставлений | Master Data EXTERNAL_MAPPING, типизированный LookupExternalMapping |
| 1 | Reporting на схеме | Reporting и reporting_db, Kafka и GraphQL-связи в исправленном PDF |
| 1 | Двойной владелец DATA_IMPORT_RUN | Независимые Production и Financial IMPORT_RUN/IMPORT_ERROR |
| 2 | Неописанный mapping RPC | Типизированный protobuf, server, client и сценарий импорта |
| 2 | Неполная база накладных | allocation_lines с заказом/центром и тремя значениями базы |
| 2 | Нет версий источников | COST_CALCULATION.source_versions и версии в событиях |
| 2 | План и cost center | plannedUnitCost, unitCostDeviation, costCenterIds, overheadAllocations |
| 2 | Несогласованные статусы | Синхронные COMPLETED/INVALIDATED, согласованные возвращаемые типы |
| 4 | Пустой импорт / retry | File adapter, транзакции фактов, ошибки, upsert и итоговый outbox |
| 4 | Экспорт остаётся QUEUED | Настоящие CSV/XLSX/PDF, file_ref и READY/FAILED |
| 4 | Пустая группа возвращает всё | [] сохраняет ограничение на уровне GraphQL, фасада и repository |
| 4 | Нет OVERHEAD_ALLOCATION | Атомарная запись всех строк вместе с калькуляцией |
| 5 | Регистрация выдаёт ANALYST | PENDING по умолчанию; операторское назначение |
| 5 | Журналы обоих контуров | Направления фильтруются по ролям, явный запрет source |
| 5 | Чужой SavedReport | Проверка владельца до создания export job |
| 6 | Обход через gRPC | Service JWT interceptor и закрытые host ports |
| 6 | Неполные consumers | Полная матрица реакций, включая ImportFailed и реальную инвалидацию Master Data |
| 6 | Ложное событие импорта | Событие соответствует сохранённому итогу и доставляется outbox |
| 6 | Reporting read model не используется | GraphQL profitability/summary маршрутизируются в Reporting |
| 6 | Последняя версия и неверный commit | Явная version события; commit только после handler/DLQ ack |
| 7 | Повтор Mutation после timeout | max_attempts=1 для изменяющих JSON RPC |
| 7 | Повреждённое сообщение / DLQ | Внутренняя десериализация и явный ack gate |
| 7 | Разрыв между сохранением и Kafka | Transactional outbox + восстановление доставки |
| 7 | Потерян correlationId | Analytics передаёт исходный correlationId |

Исполняемый код находится в итоговом проекте ЛР7. Контракты ЛР2 синхронизированы отдельно. Архивные исходники ЛР3–6 не переписывались. ЛР3 не имела замечаний; её исходный PDF сохранён без изменений. Полный набор проверок и ограничения доставки — в ../TESTING.md.
