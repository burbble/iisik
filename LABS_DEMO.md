# Демонстрация итогового проекта

Все исправления ЛР4–7 находятся здесь. Схемы данных и проектные решения ЛР1–2 отражены в исправленных PDF и пакете контрактов. Проверенные результаты приведены в TESTING.md; сверка замечаний — docs/review-fixes.md.

1. Запустить приложение по README с отдельным INTERNAL_JWT_SECRET, начальной демонстрационной БД и examples/imports.
2. Войти как production@example.local и выполнить startProductionImport(MES, 2026-10-01). Получить COMPLETED, recordsLoaded=1. Войти как finance@example.local и импортировать FINANCE за тот же период: COMPLETED, recordsLoaded=2.
3. Войти как analyst@example.local, вызвать calculateCost для PRODUCT_A за 2026-10-01 с LABOR_HOURS. Получить unitCost=35.5000, overheadCost=20.00. Через overheadAllocations увидеть заказ, центр и сумму.
4. Дождаться Kafka-проекции: profitability за октябрь вернёт revenue=640.00, costOfSales=284.00, profit=356.00. Запрос использует Reporting.
5. Выполнить exportReport для CSV, XLSX и PDF; проверить READY, fileRef и файлы в runtime-data/exports.
6. Проверить source FINANCE с производственной ролью, чужой reportId и финансовую аналитику пользователя после публичной регистрации: доступ запрещён. Новая регистрация имеет только PENDING.
7. Пустая groupIds-ссылка и productIds=[] дают пустой список/нулевую сводку.
8. За сентябрь существует утверждённый план: calculateCost и costBreakdown возвращают plannedUnitCost и unitCostDeviation. costCenterIds фильтрует продукцию по участию центра в распределении.
9. Для проверки восстановления остановить Kafka только в изолированном демонстрационном окружении. CalculateCost сохраняет результат и pending outbox. После восстановления брокера событие доставляется автоматически.

PRODUCT_A = 22222222-2222-2222-2222-222222222222; PRODUCT_B = 33333333-3333-3333-3333-333333333333. Пароль демонстрационных пользователей — Lab5Password!.

Примеры GraphQL находятся в docs/graphql_examples.graphql. Retry импортов проверяйте на исправленном снимке после FAILED: при отсутствии файла повтор корректно остаётся FAILED, а не выдаёт пустой успех.
