# ЛР7. Обеспечение надёжного взаимодействия сервисов и оптимизация распределённой системы

Запросы всех лабораторных на ЛР7: [LABS_DEMO.md](LABS_DEMO.md).

Готовые команды для ручной проверки: [TESTING.md](TESTING.md).

Тема проекта: **Программное средство анализа рентабельности продукции с интеграцией данных производственного и финансового учета**.

ЛР7 является продолжением того же проекта, который развивался в ЛР3-ЛР6. В ЛР6 mock-взаимодействия были заменены реальными gRPC-вызовами и Kafka. В ЛР7 поверх этой интеграции добавлены механизмы устойчивости: timeout, bounded retry, обработка ошибок Kafka, Redis cache и структурированное логирование.

## Что добавлено в ЛР7

- ограниченный timeout для всех gRPC-вызовов;
- retry только для временных gRPC-ошибок: `UNAVAILABLE`, `DEADLINE_EXCEEDED`, `RESOURCE_EXHAUSTED`, `ABORTED`;
- экспоненциальная задержка между повторными попытками;
- отсутствие retry для постоянных ошибок вроде `INVALID_ARGUMENT` и `NOT_FOUND`;
- повторная публикация Kafka-сообщения при временной ошибке producer;
- повторная обработка Kafka-сообщения consumer-ом;
- dead-letter topic `profitability.events.dlq` для poison message после исчерпания попыток;
- ручной commit Kafka offset после обработки или передачи в DLQ;
- Redis cache для часто используемого `GetCostingContext`;
- TTL cache-записей;
- инвалидация costing context cache при событии `MasterDataChanged`;
- graceful degradation: при ошибке Redis система продолжает работу без кеша;
- JSON-логирование gRPC, Kafka, cache hit/miss, retry и ошибок;
- сохранена безопасность из ЛР5 и реальное gRPC/Kafka взаимодействие из ЛР6;
- ключевые бизнес-сценарии продолжают выполняться через реальные сервисы.

## Основной execution flow

```text
Client
  -> GraphQL Gateway
      -> Auth Service / Redis sessions
      -> Costing Service (gRPC with timeout/retry)
          -> Master Data Service (gRPC)
               -> Redis cache for costing context
          -> Production Service (gRPC)
          -> Financial Service (gRPC)
          -> costing.db
          -> Kafka producer with bounded retry
              -> CostCalculationCompleted
                  -> Analytics consumer with retry
                      -> Costing Service (gRPC)
                      -> Financial Service (gRPC)
                      -> analytics.db
                      -> ProfitabilityCalculated
                          -> Reporting consumer
                              -> reporting.db

Kafka poison message after all attempts
  -> profitability.events.dlq
```

## gRPC resilience

Общий механизм находится в `app/shared/resilience.py`.

Параметры задаются через environment:

```text
GRPC_TIMEOUT_SECONDS=2.0
GRPC_MAX_ATTEMPTS=3
GRPC_RETRY_BACKOFF_SECONDS=0.05
```

Retry выполняется только для временных transport errors. Бизнес-ошибки и невалидные запросы повторно не отправляются.

## Kafka resilience

`KafkaEventPublisher` ограниченно повторяет публикацию сообщения. `KafkaEventConsumer` повторяет handler при ошибке и после исчерпания попыток переносит исходное событие в dead-letter topic.

```text
KAFKA_MAX_ATTEMPTS=3
KAFKA_RETRY_BACKOFF_SECONDS=0.10
KAFKA_DEAD_LETTER_TOPIC=profitability.events.dlq
```

## Redis cache

Для Costing Service кешируется нормативный контекст продукта, так как эти данные читаются при каждом расчете себестоимости, но изменяются значительно реже, чем выполняются расчеты.

Ключ:

```text
costing-context:<product_id>:<period>
```

TTL по умолчанию:

```text
300 секунд
```

При `MasterDataChanged` costing consumer удаляет записи с префиксом `costing-context:`. Если Redis временно недоступен, cache layer логирует ошибку и выполняет обычный gRPC-вызов без кеша.

## Логирование

Логи выводятся в JSON. Для каждой важной операции фиксируются, где применимо:

- время;
- уровень;
- сервис / logger;
- операция;
- target;
- номер попытки;
- длительность;
- Kafka event type;
- correlation id;
- тип ошибки.

Это позволяет проследить, на каком этапе распределенного сценария произошла ошибка.

## Структура новых компонентов

```text
app/shared/
├── cache.py              # Redis / memory / null cache
├── logging_config.py     # JSON logging
└── resilience.py         # timeout + bounded gRPC retry

app/transport/grpc/
├── bridge.py             # resilient Gateway -> service gRPC
└── domain_clients.py     # resilient typed service-to-service gRPC + cache

app/transport/kafka/
├── publisher.py          # bounded publish retry
└── consumer.py           # handler retry + DLQ + manual commit
```

Остальная структура проекта сохранена из ЛР6.

## Docker Compose

Kafka: `apache/kafka:3.9.1` в KRaft-режиме. Compose ждёт готовности Kafka, Redis и серверов приложения. Redis доступен с хоста на `16379` (можно изменить через `REDIS_PORT`), внутри сети — на `redis:6379`.

В `docker-compose.yml` находятся:

- Redis;
- Kafka;
- Auth Service;
- GraphQL Gateway;
- Master Data;
- Production;
- Financial;
- Costing;
- Analytics;
- Reporting.

Запуск:

```bash
docker compose build
docker compose run --rm auth python -m app.scripts.seed
docker compose up -d --wait --wait-timeout 180
```

GraphQL endpoint:

```text
http://127.0.0.1:8000/graphql
```

## Тесты

Без внешнего Kafka/Redis тесты используют in-memory backends:

```bash
LAB7_EVENT_BACKEND=memory \
LAB7_SESSION_BACKEND=memory \
LAB7_CACHE_BACKEND=memory \
python -m pytest -q
```

Результат при сборке ЛР7:

```text
37 passed
```

Дополнительно проверяется:

- восстановление gRPC-вызова после временных ошибок;
- отсутствие retry для постоянной ошибки;
- применение timeout на каждой попытке;
- cache hit без повторного сетевого вызова;
- инвалидация cache;
- bounded retry Kafka producer;
- retry Kafka consumer handler;
- передача poison message в dead-letter flow;
- прежние GraphQL, security, business logic и реальные gRPC-сценарии.

## Важное ограничение тестового окружения

Автотесты не поднимают настоящий Kafka broker и Redis server. Для broker-level и Redis-level проверки используется `docker-compose.yml`. Unit/integration tests проверяют логику retry, cache API и gRPC network calls без зависимости от внешней инфраструктуры.
