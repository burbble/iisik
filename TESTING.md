# Проверка итоговой версии

Проверка выполнена 31 октября 2026 года. Последний полный unit/integration прогон: **61 passed**. Использован Python 3.12, установлены зависимости requirements.txt. Тесты запускают реальные gRPC server/client; session, cache и event publisher используют memory backends. Kafka consumer дополнительно проверяется на управляемых сырых записях и явных offsets.

```bash
LAB7_DATA_DIR=/tmp/iisik-test-data \
LAB7_EVENT_BACKEND=memory LAB7_SESSION_BACKEND=memory \
LAB7_CACHE_BACKEND=memory python -m pytest -q
```

Регрессии преподавательских замечаний находятся в `tests/test_review_fixes.py`: регистрация PENDING, фильтр направлений импорта, чужой SavedReport без создания задания, файлы трёх форматов и ошибка диска, сохранение фактов/откат/повтор импорта, пустая группа, распределения и версии источников, служебная gRPC-аутентификация, отсутствие retry Mutation, outbox при отказе брокера, неуспешный DLQ, повреждённые bytes и commit конкретной позиции, точная версия калькуляции и correlationId, инвалидация Master Data, фильтр центра затрат и защита проекции от старой версии.

## Проверка настоящих Kafka и Redis

В отдельном Compose-проекте с изолированным каталогом данных выполнено:

1. Запущены Kafka 3.9.1, Redis 7, Auth, Gateway и шесть gRPC-сервисов; все healthchecks прошли.
2. Выполнены login трёх бухгалтерских/аналитических пользователей и импорт за 2026-10-01: Production COMPLETED, recordsLoaded=1; Financial COMPLETED, recordsLoaded=2.
3. CalculateCost: выпуск 10, материалы 185, труд 150, накладные 20; unitCost=35.5000.
4. Kafka → Analytics → Reporting → GraphQL: выручка 640.00, стоимость продаж 284.00, прибыль 356.00.
5. CSV, XLSX и PDF экспорты завершились READY с существующими файлами.
6. Пустая группа вернула count=0; запрос FINANCE от производственного бухгалтера отклонён; публичный register вернул PENDING, финансовая аналитика новому пользователю запрещена.
7. Kafka остановлена. CalculateCost за сентябрь завершился и сохранил версию 2, unitCost=46.0000; в outbox осталась одна pending-запись.
8. Kafka запущена снова. Pending outbox автоматически доставлен, число pending-записей стало 0.

Проверка не заявляет exactly-once: crash между подтверждением брокера и отметкой outbox допускает повтор. Восстановление основано на сохранённом событии и повторяемых обработчиках.

Для обычного запуска следуйте README. Seed очищает демонстрационную БД; для проверки используйте отдельный каталог данных. В Compose задайте INTERNAL_JWT_SECRET. Пример пользовательских GraphQL-команд — `docs/graphql_examples.graphql`, пример снимков — `examples/imports`.
