# Межсервисное взаимодействие ЛР6

## Синхронный сценарий расчета себестоимости

1. Клиент вызывает GraphQL Mutation `calculateCost`.
2. GraphQL Gateway после проверки JWT вызывает Costing Service по gRPC.
3. Costing Service вызывает `MasterDataService.GetCostingContext`.
4. Costing Service вызывает `ProductionDataService.GetProductionCostData`.
5. Costing Service вызывает `FinancialDataService.GetOverheadData`.
6. Costing Service выполняет расчет и сохраняет новую версию в `costing.db`.
7. Costing Service публикует `CostCalculationCompleted` в Kafka.

## Асинхронное продолжение

1. Analytics consumer получает `CostCalculationCompleted`.
2. Analytics Service по gRPC получает утвержденную себестоимость из Costing Service.
3. Analytics Service по gRPC получает продажи из Financial Service.
4. Сохраняется `PROFITABILITY_RESULT`.
5. Публикуется `ProfitabilityCalculated`.
6. Reporting consumer получает событие и обновляет `PROFITABILITY_READ_MODEL`.

Таким образом один бизнес-сценарий содержит и gRPC, и Kafka, а Kafka не используется отдельно от прикладной логики.
