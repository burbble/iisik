# Архитектура ЛР4

ЛР4 продолжает структуру ЛР3. Реальное сетевое взаимодействие между микросервисами пока не используется.

```text
Web client
   |
   v
GraphQL Gateway
   |
   v
ApplicationFacade
   |
   +--> MockMasterDataClient ------> MasterDataService ------> master_data.db
   +--> MockProductionClient ------> ProductionService ------> production.db
   +--> MockFinancialClient -------> FinancialService -------> finance.db
   +--> MockCostingClient ---------> CostingService ---------> costing.db
   +--> MockAnalyticsClient -------> AnalyticsService -------> analytics.db
   +--> MockReportingClient -------> ReportingService -------> reporting.db
```

Resolvers только принимают GraphQL-запрос, преобразуют типы и вызывают фасад. Проверки бизнес-условий и изменение состояния находятся в сервисном слое.

Новые операции ЛР4:

- запуск производственного и финансового импорта;
- повтор неудачного импорта;
- разрешение сопоставления внешнего кода;
- перерасчет себестоимости с распределением накладных расходов;
- перерасчет рентабельности;
- создание задания на экспорт отчета;
- фильтрация и сортировка Query;
- агрегирование рентабельности.
