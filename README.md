# ЛР7 Анализ рентабельности продукции

Итоговый проект лабораторных 3–7. Исправления бизнес-операций, безопасности и распределённого обмена собраны в этой версии. Отчёты ЛР1–7 подготовлены отдельно в PDF с исходными титульными страницами.

## Запуск

```bash
cp .env.example .env
# Задайте в .env случайный INTERNAL_JWT_SECRET длиной не менее 32 символов.
docker compose build
docker compose run --rm auth python -m app.scripts.seed
docker compose up -d --wait --wait-timeout 180
```

Seed создаёт демонстрационные данные и очищает прежние данные приложения; выполняйте его только для начального демонстрационного развёртывания. GraphQL: http://127.0.0.1:8000/graphql. Учётные записи: analyst@example.local, production@example.local, finance@example.local, manager@example.local, admin@example.local; демонстрационный пароль `Lab5Password!`.

Внутренние gRPC-порты не опубликованы. Каждый RPC требует отдельный служебный JWT; изменяющие методы может инициировать только gateway. Пользовательский JWT проверяется Auth Service вместе с активной Redis-сессией и актуальными ролями. Публичная регистрация даёт только PENDING. Назначение бизнес-роли оператором:

```bash
docker compose exec auth python -m app.scripts.assign_role user@example.local ANALYST
```

## Реальные бизнес-операции

Импорт читает JSON-массив `IMPORT_DATA_DIR/<SOURCE>/<YYYY-MM-01>.json`. В Compose `examples/imports` подключён как `/imports`: там есть ERP, MES и FINANCE за октябрь 2026 года. Производственная запись содержит заказ, материалы и труд; финансовая — SALE, OVERHEAD либо CORRECTION. Все внешние коды разрешаются через типизированный MasterDataService.LookupExternalMapping. Ошибка заказа откатывает его дочерние записи. Счётчики и ошибки сохраняются; итог COMPLETED либо FAILED. Повтор исправленного снимка использует стабильные внешние ключи без дубликатов.

Costing получает реальную базу по заказам и центрам затрат, распределяет финансовые нетто-суммы по выбранной базе, сохраняет OVERHEAD_ALLOCATION вместе с калькуляцией и версиями источников. Утверждённый план принадлежит Master Data (PLANNED_COST). CostBreakdown возвращает plannedUnitCost и unitCostDeviation; без плана — null. overheadAllocations раскрывает распределения по заказам/центрам. costCenterIds в фильтре рентабельности выбирает участвующую продукцию; прибыль остаётся показателем продукта.

Reporting формирует CSV/XLSX/PDF, проверяет владельца SavedReport до создания задания, записывает временный файл и атомарно переименовывает его. READY содержит file_ref; FAILED — error_message. Файлы находятся в `runtime-data/exports`.

profitability и profitabilitySummary читают reporting.db через ReportingGateway. Пустая группа или productIds=[] даёт пустой список и нулевую сводку. Выдача обновляется асинхронно по Kafka; скрытого обхода витрины через Analytics нет.

## Согласованность и восстановление

Калькуляция, детализация и CostCalculationCompleted сохраняются одной транзакцией с OUTBOX_EVENT. Фоновый dispatcher повторяет доставку после отказа Kafka и перезапуска. Итоги импортов используют такой же локальный outbox. Доставка как минимум один раз; возможный дубликат сохраняет eventId. Analytics обновляет результат по calculation_id, Reporting обновляет продукт/период и не заменяет новую cost_version более старым событием.

Analytics использует version из CostCalculationCompleted и наследует correlationId для ProfitabilityCalculated. Изменение источников и MasterDataChanged инвалидирует зависимые результаты; MasterDataChanged также очищает кеш нормативов. Статусы синхронных CalculationJob: COMPLETED и INVALIDATED. Ошибка расчёта возвращается ошибкой операции.

Читающие gRPC имеют timeout и bounded retry, изменяющие операции автоматически не повторяются. Kafka consumer декодирует каждую запись внутри error boundary, передаёт повреждённые bytes в DLQ и подтверждает только конкретный offset после handler success либо подтверждённого DLQ. При отказе обеих операций позиция не подтверждается.

## Проверка

```bash
pip install -r requirements.txt
LAB7_EVENT_BACKEND=memory LAB7_SESSION_BACKEND=memory LAB7_CACHE_BACKEND=memory python -m pytest -q
```

Результат и отдельный Compose-сценарий: [TESTING.md](TESTING.md). Подробная сверка замечаний: [docs/review-fixes.md](docs/review-fixes.md). Контракты: `docs/schema.graphql`, `docs/proto/profitability.proto`, `docs/proto/gateway_bridge.proto`.

## Отчёты и технический проект

Исправленные PDF ЛР1–7 с исходными титульными страницами находятся в [reports](reports/). ЛР3 не имела замечаний и сохранена без изменений. Согласованные SQL, protobuf, GraphQL и примеры событий ЛР2 — в [docs/design-lab2](docs/design-lab2/). Полная сверка исправлений: [docs/review-fixes.md](docs/review-fixes.md).
