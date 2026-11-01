# Надёжность

Читающие gRPC (Get/List/Lookup и ProfitabilitySummary) используют timeout каждой попытки, до трёх повторов временных транспортных ошибок и экспоненциальную задержку. Изменяющие RPC имеют ровно одну автоматическую попытку. Timeout изменения означает неизвестный клиенту результат; он не запускает новый CalculateCost автоматически.

Transactional outbox хранит событие в одной транзакции с калькуляцией и распределениями. Pending события переживают отказ Kafka и перезапуск процесса; dispatcher повторяет доставку. Только подтверждённая публикация отмечается published_at. Между broker ack и отметкой возможен повтор — доставка at-least-once, без обещания exactly-once. Аналогично фиксируются итоги импортов.

Kafka consumer не подтверждает offset, если handler и DLQ не завершились успешно. Ошибки десериализации находятся внутри error boundary; повреждённая запись передаётся в DLQ вместе с исходными bytes. Commit привязан к конкретной partition/позиции; более поздняя запись не подтверждается поверх недоставленной.

Analytics читает точную версию себестоимости из CostCalculationCompleted. ProfitabilityCalculated наследует correlationId. Reporting сравнивает cost_version, поэтому поздний старый результат не перезаписывает новую проекцию. Инвалидация справочников очищает кеш и помечает калькуляции INVALIDATED.

Redis costing-context:<product_id>:<period> имеет TTL 300 секунд. Ошибка кеша логируется и приводит к исходному gRPC-чтению. JSON-логи содержат operation, target, attempt, duration_ms, event_type, correlation_id и error_type.

Проверки и результат фактического отключения Kafka приведены в ../TESTING.md.
