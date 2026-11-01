# gRPC и Kafka

Типизированные RPC определены в proto/profitability.proto. LookupExternalMapping(source_system, entity_type, external_code) возвращает internal_id и mapping_version. GetProductionCostData возвращает агрегаты и allocation_lines: production_order_id, cost_center_id, volume, labor_hours, direct_cost. База выбирается согласно allocationBase. GetOverheadData возвращает нетто-суммы OVERHEAD+CORRECTION по центру, correction_amount=0. GetApprovedCostCalculation принимает явную версию; INVALIDATED отклоняется.

Версия нормативов — hash данных Master Data. Версия импорта — идентификатор запуска вместе с временем завершения попытки; retry того же IMPORT_RUN меняет ревизию. Эти версии и версия плана сохраняются в COST_CALCULATION.source_versions.

| Событие | Реакция |
|---|---|
| ProductionDataImported | Готовность Production в Costing, инвалидация прежних калькуляций/аналитики/витрины за период |
| FinancialDataImported | Готовность Financial и аналогичная инвалидация |
| ImportFailed | Сброс готовности контура, инвалидация зависимых результатов |
| MasterDataChanged | Инвалидация калькуляций и нормативного кеша; инвалидация Analytics и Reporting |
| CostCalculationCompleted | Analytics рассчитывает именно version из события; Reporting ожидает новый результат |
| ProfitabilityCalculated | Reporting обновляет продукт/период; более старая costVersion не заменяет новую |

Импорт сохраняет факты, ошибки и итоговый статус; событие итога добавляется в локальный outbox. Costing атомарно сохраняет калькуляции, детали распределения и EventEnvelope в outbox. Dispatcher доставляет pending после восстановления брокера. События CostCalculationCompleted пакета имеют общий correlationId, который Analytics сохраняет в ProfitabilityCalculated.

Kafka consumer читает bytes, валидирует envelope и обрабатывает ошибки декодирования внутри записи. Handler retry → подтверждённый DLQ → commit конкретного offset+1. Если DLQ недоступна, позиция не подтверждается и consumer повторяет текущую запись. Повреждённые bytes доступны в DLQ в base64.

ReportingGateway.ListProfitability/ProfitabilitySummary используются внешним GraphQL; прямой список Analytics не подменяет витрину. Фильтрация и сводка согласованы, выдача обновляется асинхронно.
