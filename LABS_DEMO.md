# Демонстрация лабораторных 2–7 на приложении ЛР7

Запускается только проект ЛР7. Ниже запросы разделены по этапам, но все соответствуют текущей схеме ЛР7. В этой версии каждый защищённый запрос требует токен; он получается автоматически. ID, даты и пароли уже подставлены, новые ID извлекаются из ответов.

Раздел ЛР5 описывает авторизацию, реализованную в ЛР7: отдельной папки ЛР5 в рабочей папке нет. В ЛР2 был технический проект, поэтому её раздел показывает контракты. Для ЛР3–4 показываем функции в современной версии, а не старую mock-архитектуру.

Нужны Docker Compose, `curl` и Python 3. Все блоки запросов копируй по порядку в один Bash/Zsh-терминал из папки проекта. Можно демонстрировать отдельную лабу после раздела подготовки; ЛР6 содержит самостоятельный сценарий, не зависящий от мутаций ЛР4.

## Запуск последней лабораторной

Выполняй команды из корня клонированного репозитория.

```bash
docker compose build
docker compose run --rm auth python -m app.scripts.seed
docker compose up -d --wait --wait-timeout 180
docker compose ps
```

Команда `seed` сбрасывает демонстрационные данные в `runtime-data`. Если приложение уже запущено и нужно начать демонстрацию заново, сначала выполни `docker compose down`, затем команды заполнения и запуска. Для обычного повторного запуска без сброса достаточно `docker compose up -d --wait --wait-timeout 180`.

GraphQL: `http://127.0.0.1:8000/graphql`. Настоящие Kafka, Redis и gRPC запускаются в Compose; Redis с хоста — `16379`, внутри сети — `redis:6379`.

## Подготовка: функции и автоматический вход

Скопируй целиком один раз. `gql` отправляет JSON через `curl` и печатает ответ. Если опубликованный HTTP-порт недоступен с хоста, автоматически используется тот же HTTP API из контейнера `gateway`; это позволяет выполнять команды, если опубликованные Docker-порты недоступны с хоста. Подмена бизнес-логики или данных при этом не выполняется.

После этого в примерах используется короткое `gql` вместо повторения одинаковых заголовков `curl`. Токен живёт час; `login admin` получает новый токен, `login analyst` / `login production` / `login finance` / `login manager` переключают демонстрационного пользователя.

```bash
set -o pipefail
API=http://127.0.0.1:8000/graphql
TOKEN=
if curl --fail --silent --max-time 3 http://127.0.0.1:8000/health >/dev/null; then
  USE_DOCKER_HTTP=0
  printf 'HTTP доступен с хоста.\n'
else
  USE_DOCKER_HTTP=1
  printf 'Используем HTTP из gateway через docker compose exec.\n'
fi
post_graphql() {
  if [ "$USE_DOCKER_HTTP" = 1 ]; then
    docker compose exec -T -e DEMO_TOKEN="${TOKEN:-}" gateway python -c '
import os, sys, urllib.request, urllib.error
headers = {"Content-Type": "application/json"}
if os.environ.get("DEMO_TOKEN"):
    headers["Authorization"] = "Bearer " + os.environ["DEMO_TOKEN"]
request = urllib.request.Request("http://127.0.0.1:8000/graphql", data=sys.stdin.buffer.read(), headers=headers)
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        print(response.read().decode())
except urllib.error.HTTPError as error:
    print(error.read().decode())
    sys.exit(22)
'
  else
    local -a headers=(-H 'Content-Type: application/json')
    if [ -n "${TOKEN:-}" ]; then
      headers+=(-H "Authorization: Bearer $TOKEN")
    fi
    curl --fail-with-body --silent --show-error --max-time 20 "$API" "${headers[@]}" --data-binary @-
  fi
}
gql() {
  post_graphql | python3 -c '
import json, sys
raw = sys.stdin.read()
if not raw.strip():
    print("API не вернул ответ. Убедись, что Compose запущен из папки ЛР7.", file=sys.stderr)
    sys.exit(1)
try:
    body = json.loads(raw)
except json.JSONDecodeError:
    print("API вернул ответ не в формате JSON:", raw, file=sys.stderr)
    sys.exit(1)
print(json.dumps(body, ensure_ascii=False, indent=2))
if body.get("errors"):
    sys.exit(1)
'
}
login() {
  local saved_token="${TOKEN:-}" reply
  TOKEN=
  reply=$(python3 -c '
import json, sys
print(json.dumps({
    "query": "mutation Login($input: CredentialsInput!) { login(input:$input) { accessToken user { email roles } } }",
    "variables": {"input": {"email": sys.argv[1] + "@example.local", "password": "Lab5Password!"}},
}))
' "${1:-admin}" | gql) || {
    TOKEN="$saved_token"
    return 1
  }
  TOKEN=$(printf '%s' "$reply" | python3 -c 'import json, sys; print(json.load(sys.stdin)["data"]["login"]["accessToken"])') || return 1
  export TOKEN
  printf 'Вход выполнен: %s@example.local; токен сохранён автоматически.\n' "${1:-admin}"
}
login admin
```

## ЛР2 — контракты системы

Здесь нет собственных бизнес-операций: демонстрируем внешнюю GraphQL-схему, gRPC/protobuf и формат Kafka-событий, использованные в реализации. Это версии контрактов из ЛР7; исходные файлы ЛР2 остаются в её папке.

### GraphQL: какие Query и Mutation доступны

Ожидаются `products`, `costBreakdown`, `profitability`, импорт, расчёты и операции авторизации.

```bash
gql <<'JSON'
{"query": "{ __schema { queryType { name fields { name } } mutationType { name fields { name } } } }"}
JSON
```

Контракты gRPC и Kafka без ручного поиска файлов:

```bash
docker compose exec -T gateway cat docs/proto/profitability.proto
docker compose exec -T gateway cat docs/kafka/event-envelope.schema.json
docker compose exec -T gateway cat docs/kafka/examples/cost-calculation-completed.json
```

## ЛР3 — чтение данных через GraphQL

После свежего `seed`: два продукта, расчёты и импорт за сентябрь 2026 года.

### Продукция

Ожидаются `PD-1` и `DET-01`.

```bash
gql <<'JSON'
{"query": "{ products(filter:{active:true}) { id code name groupId unit active } }"}
JSON
```

### История производственного импорта

Есть завершённый импорт ERP.

```bash
gql <<'JSON'
{"query": "{ importRuns(source:ERP,period:\"2026-09-01\") { id source period status recordsLoaded recordsFailed errors { errorCode message } } }"}
JSON
```

### Детализация себестоимости

До пересчёта: `totalCost = 4000`, `unitCost = 40`.

```bash
gql <<'JSON'
{"query": "{ costBreakdown(productId:\"22222222-2222-2222-2222-222222222222\",period:\"2026-09-01\") { calculationId productId version materialCost laborCost overheadCost totalCost producedQty unitCost } }"}
JSON
```

### Рентабельность

До пересчёта: прибыли `3200` и `3150`.

```bash
gql <<'JSON'
{"query": "{ profitability(filter:{periodFrom:\"2026-09-01\",periodTo:\"2026-09-30\"}) { id productId revenue costOfSales profit marginPercent } }"}
JSON
```

### Статус расчёта

Ожидается `COMPLETED`.

```bash
gql <<'JSON'
{"query": "{ calculationStatus(id:\"88888888-8888-8888-8888-888888888888\") { id status period productIds } }"}
JSON
```

### Демонстрационная запись экспорта

Администратор может прочитать эту запись другого пользователя. `READY` и путь к XLSX — заранее заполненные данные, а не проверка существования файла.

```bash
gql <<'JSON'
{"query": "{ reportExport(id:\"99999999-9999-9999-9999-999999999999\") { id status format fileRef errorMessage } }"}
JSON
```

## ЛР4 — бизнес-операции, фильтры и агрегаты

Эти запросы меняют тестовые данные. В ЛР7 импорт завершается демонстрационным обработчиком с `recordsLoaded = 0`; внешняя ERP/MES/финансовая система не опрашивается.

### Фильтрация и сортировка

Подходящие продукты отсортированы по имени.

```bash
gql <<'JSON'
{"query": "{ products(filter:{active:true,search:\"П\"},sort:{field:NAME,direction:ASC}) { id code name } }"}
JSON
```

### Фильтр и сортировка рентабельности

Маржа не ниже 40%, сортировка по убыванию.

```bash
gql <<'JSON'
{"query": "{ profitability(filter:{periodFrom:\"2026-09-01\",periodTo:\"2026-09-30\",minMarginPercent:40},sort:{field:MARGIN_PERCENT,direction:DESC}) { productId profit marginPercent } }"}
JSON
```

### Агрегаты

До новых расчётов: `count = 2`, `totalRevenue = 12400`, `totalCost = 6050`, `totalProfit = 6350`. После расчётов агрегаты учитывают хранимые результаты.

```bash
gql <<'JSON'
{"query": "{ profitabilitySummary(filter:{periodFrom:\"2026-09-01\",periodTo:\"2026-09-30\"}) { count totalRevenue totalCost totalProfit averageMarginPercent } }"}
JSON
```

### Производственный импорт

Ожидается `COMPLETED`.

```bash
gql <<'JSON'
{"query": "mutation { startProductionImport(input:{source:MES,period:\"2026-10-01\"}) { id source period status recordsLoaded } }"}
JSON
```

### Финансовый импорт

Ожидается `COMPLETED`.

```bash
gql <<'JSON'
{"query": "mutation { startFinancialImport(input:{source:FINANCE,period:\"2026-10-01\"}) { id source period status recordsLoaded } }"}
JSON
```

### Повтор неудачного импорта

Ожидается `COMPLETED`. Этот блок успешно выполняется один раз после `seed`: после повтора импорт больше не `FAILED`.

```bash
gql <<'JSON'
{"query": "mutation { retryImport(id:\"eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeef\") { id source period status } }"}
JSON
```

### Сопоставить внешний код

Ожидается `RESOLVED`.

```bash
gql <<'JSON'
{"query": "mutation { resolveExternalMapping(input:{sourceSystem:\"MES\",entityType:\"PRODUCT\",externalCode:\"MES-DET-01\",internalId:\"33333333-3333-3333-3333-333333333333\"}) { id status externalCode internalId } }"}
JSON
```

### Рассчитать себестоимость

Новые версии: `PD-1` — `4040` и `40.4`; `DET-01` — `3760` и `18.8`. В ЛР7 дополнительно публикуются Kafka-события.

```bash
gql <<'JSON'
{"query": "mutation { calculateCost(input:{period:\"2026-09-01\",productIds:[\"22222222-2222-2222-2222-222222222222\",\"33333333-3333-3333-3333-333333333333\"],allocationBase:\"LABOR_HOURS\"}) { calculationId productId version totalCost unitCost } }"}
JSON
```

### Явно рассчитать рентабельность

Ожидается `COMPLETED`. Эта Mutation показывает операцию ЛР4; отдельный раздел ЛР6 ниже проверяет именно автоматическое выполнение через Kafka.

```bash
gql <<'JSON'
{"query": "mutation { calculateProfitability(input:{period:\"2026-09-01\",productIds:[\"22222222-2222-2222-2222-222222222222\",\"33333333-3333-3333-3333-333333333333\"]}) { id status period productIds } }"}
JSON
```

### Посмотреть результаты

Новые результаты имеют прибыли `3168` и `3180`; история старых результатов может сохраняться.

```bash
gql <<'JSON'
{"query": "{ profitability(filter:{periodFrom:\"2026-09-01\",periodTo:\"2026-09-30\"}) { id productId revenue costOfSales profit marginPercent } }"}
JSON
```

### Создать экспорт и прочитать его статус без копирования ID

В текущем API `requestedBy` не передаётся: пользователь определяется по токену. Новый экспорт получает `QUEUED`, `fileRef = null`. В этом проекте создаётся задание; генератор файлов и endpoint скачивания отсутствуют.

```bash
EXPORT_REPLY=$(gql <<'JSON'
{"query":"mutation { exportReport(input:{format:XLSX}) { id status format fileRef } }"}
JSON
) && {
  printf '%s
' "$EXPORT_REPLY"
  EXPORT_ID=$(printf '%s' "$EXPORT_REPLY" | python3 -c 'import json, sys; print(json.load(sys.stdin)["data"]["exportReport"]["id"])')
  gql <<JSON
{"query":"{ reportExport(id:\"$EXPORT_ID\") { id status format fileRef errorMessage } }"}
JSON
}
```

### Проверка бизнес-ошибки

Это ожидаемая ошибка `productIds cannot be empty`. Функция вернёт ненулевой код; сам сервер продолжит работу.

```bash
gql <<'JSON'
{"query": "mutation { calculateCost(input:{period:\"2026-09-01\",productIds:[],allocationBase:\"LABOR_HOURS\"}) { productId } }"}
JSON
```

## ЛР5 — авторизация, роли и Redis-сессии

Эта функциональность сохранена в ЛР7. Все тестовые пользователи уже созданы `seed`; пароль подставляет функция `login`.

```bash
login analyst
```

### Текущий пользователь

Ожидается `analyst@example.local` и роль `ANALYST`.

```bash
gql <<'JSON'
{"query": "{ me { id email roles } }"}
JSON
```

### Операция без нужной роли

Ожидаемая ошибка: `Operation is not allowed for current role`. Для аналитика производственный импорт запрещён; новых записей не создаётся.

```bash
gql <<'JSON'
{"query": "mutation { startProductionImport(input:{source:MES,period:\"2026-11-01\"}) { id status } }"}
JSON
```

```bash
login production
```

### Та же операция с разрешённой ролью

Теперь импорт разрешён, ожидается `COMPLETED`.

```bash
gql <<'JSON'
{"query": "mutation { startProductionImport(input:{source:MES,period:\"2026-11-01\"}) { id status } }"}
JSON
```

### Регистрация с автоматически созданным уникальным email

Создаётся ещё один тестовый пользователь с ролью `ANALYST`. Email придумывать не нужно.

```bash
python3 - <<'PYTHON' | gql
import json, uuid
email = 'demo.lab5.' + uuid.uuid4().hex + '@example.local'
query = 'mutation { register(input:{email:' + json.dumps(email) + ',password:"StrongPass123!"}) { id email roles } }'
print(json.dumps({'query': query}))
PYTHON
```

### Выход, отказ отозванному токену, новый вход

Первый ответ — `logout = true`. Проверка старого токена должна вернуть HTTP `401`; после нового входа остальные разделы снова работают.

```bash
gql <<'JSON'
{"query":"mutation { logout }"}
JSON
if post_graphql <<'JSON'
{"query":"{ me { id } }"}
JSON
then
  printf '
ОШИБКА: отозванный токен был принят.
'
else
  printf '
Ожидаемый отказ после logout (HTTP 401).
'
fi
login admin
```

## ЛР6 — настоящее gRPC и события Kafka

Сценарий самостоятельный: повторный расчёт создаёт новые ID, и проверяются только эти новые записи. Даже после раздела ЛР4 старые результаты не смогут выдать ложный успех. Явный `calculateProfitability` в этом разделе не вызывается.

### Расчёт себестоимости и автоматическое получение его ID

```bash
COST_REPLY=$(gql <<'JSON'
{"query": "mutation { calculateCost(input:{period:\"2026-09-01\",productIds:[\"22222222-2222-2222-2222-222222222222\",\"33333333-3333-3333-3333-333333333333\"],allocationBase:\"LABOR_HOURS\"}) { calculationId productId version totalCost unitCost } }"}
JSON
) && {
  printf '%s\n' "$COST_REPLY"
  COST_IDS=$(printf '%s' "$COST_REPLY" | python3 -c 'import json, sys; print(json.dumps([row["calculationId"] for row in json.load(sys.stdin)["data"]["calculateCost"]]))')
  export COST_IDS
}
```

### Дождаться Analytics и Reporting через Kafka

Команда проверяет новые записи SQLite в тестовой системе. Это диагностическая проверка результата; бизнес-операция выше прошла через HTTP → Gateway → gRPC → Kafka. Ожидаются две новые записи рентабельности с прибылью `3168`/`3180` и две соответствующие строки проекции отчёта.

```bash
docker compose exec -T -e DEMO_COST_IDS="$COST_IDS" gateway python - <<'PYTHON'
import json, os, sqlite3, time
ids = json.loads(os.environ['DEMO_COST_IDS'])
assert len(ids) == 2, 'Нужно сначала выполнить расчёт двух продуктов'
for attempt in range(120):
    with sqlite3.connect('/data/analytics.db') as db:
        rows = db.execute('SELECT result_id, profit FROM profitability_results WHERE calculation_id IN (?, ?)', ids).fetchall()
    if len(rows) == 2:
        break
    time.sleep(0.25)
else:
    raise RuntimeError('Не пришли новые результаты Analytics: проверь Kafka и логи analytics')
assert sorted(float(row[1]) for row in rows) == [3168.0, 3180.0], rows
print('OK: Kafka автоматически рассчитала рентабельность для новых calculationId')
result_ids = [row[0] for row in rows]
for attempt in range(120):
    with sqlite3.connect('/data/reporting.db') as db:
        projection = db.execute('SELECT source_result_id, profit FROM profitability_read_model WHERE source_result_id IN (?, ?)', result_ids).fetchall()
    if len(projection) == 2:
        break
    time.sleep(0.25)
else:
    raise RuntimeError('Reporting не получил событие: проверь логи reporting')
assert sorted(float(row[1]) for row in projection) == [3168.0, 3180.0], projection
print('OK: Kafka обновила проекцию отчёта для новых resultId')
PYTHON
```

### Посмотреть события и сервисы

```bash
docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh   --bootstrap-server kafka:9092 --topic profitability.events   --from-beginning --max-messages 3 --timeout-ms 10000
docker compose ps
```

## ЛР7 — кеш, инвалидация, повторные попытки и DLQ

Для раздела кеша сначала выполни расчёт себестоимости из ЛР6: он заполняет costing context cache.

### Redis-кеш и TTL

Есть ключи контекста продуктов, TTL положительный и не больше 300 секунд. `-2` означает, что кеш уже истёк: повтори расчёт себестоимости, затем эту проверку.

```bash
docker compose exec -T redis redis-cli --scan --pattern 'lab7:cache:costing-context:*'
docker compose exec -T redis redis-cli TTL 'lab7:cache:costing-context:22222222-2222-2222-2222-222222222222:2026-09-01'
```

### Повторный расчёт использует кеш

В логах Costing должен появиться `cache hit`; данные продуктов при этом остаются теми же.

```bash
gql <<'JSON'
{"query": "mutation { calculateCost(input:{period:\"2026-09-01\",productIds:[\"22222222-2222-2222-2222-222222222222\",\"33333333-3333-3333-3333-333333333333\"],allocationBase:\"LABOR_HOURS\"}) { calculationId productId version totalCost unitCost } }"}
JSON
```

```bash
docker compose logs --tail 100 costing
```

### Изменение Master Data инвалидирует кеш

Публикуется `MasterDataChanged`; costing consumer удаляет кеш нормативного контекста.

```bash
gql <<'JSON'
{"query": "mutation { resolveExternalMapping(input:{sourceSystem:\"MES\",entityType:\"PRODUCT\",externalCode:\"MES-DET-01\",internalId:\"33333333-3333-3333-3333-333333333333\"}) { id status externalCode internalId } }"}
JSON
```

```bash
docker compose exec -T gateway python - <<'PYTHON'
import redis, time
client = redis.Redis.from_url('redis://redis:6379/0')
key = 'lab7:cache:costing-context:22222222-2222-2222-2222-222222222222:2026-09-01'
for attempt in range(120):
    if not client.exists(key):
        print('OK: кеш удалён после MasterDataChanged')
        break
    time.sleep(0.25)
else:
    raise RuntimeError('Кеш не инвалидирован: проверь costing consumer')
PYTHON
```

### Реальная проверка retry и DLQ

Отправляется одно демонстрационное событие для несуществующего продукта. Analytics повторяет обработку и переносит неуспешное событие в `profitability.events.dlq`. Команда ждёт именно своё событие по автоматически полученному ID; старые сообщения не засчитываются.

```bash
docker compose exec -T gateway python - <<'PYTHON'
import json
from kafka import KafkaConsumer
from app.transport.kafka.events import EventEnvelope
from app.transport.kafka.publisher import KafkaEventPublisher

event = EventEnvelope.create('CostCalculationCompleted', 'lab7-demo', {
    'productId': '00000000-0000-0000-0000-000000000000',
    'period': '2026-09-01',
    'calculationId': '00000000-0000-0000-0000-000000000000',
})
publisher = KafkaEventPublisher(bootstrap_servers='kafka:9092')
try:
    publisher.publish(event)
finally:
    publisher.close()
consumer = KafkaConsumer(
    'profitability.events.dlq', bootstrap_servers=['kafka:9092'],
    auto_offset_reset='earliest', enable_auto_commit=False,
    consumer_timeout_ms=30000, value_deserializer=lambda data: json.loads(data),
)
try:
    for record in consumer:
        failed = record.value
        if failed.get('payload', {}).get('originalEventId') == event.eventId:
            print(json.dumps(failed, ensure_ascii=False, indent=2))
            print('OK: своё неуспешное событие получено в DLQ после повторов')
            break
    else:
        raise RuntimeError('Свое событие не найдено в DLQ: проверь analytics')
finally:
    consumer.close()
PYTHON
```

### Проверить retry/timeout и остальные механизмы автотестами

Изолированный контейнер не публикует порты и использует отдельную временную базу. Тесты retry/timeout намеренно вызывают временные ошибки; внешние Kafka/Redis здесь заменены памятью. Реальный брокер уже проверен командами выше.

```bash
docker compose run --rm --no-deps   -e LAB7_DATA_DIR=/tmp/lab-tests   -e LAB7_EVENT_BACKEND=memory -e LAB7_SESSION_BACKEND=memory   -e LAB7_CACHE_BACKEND=memory   auth python -m pytest -q tests/test_resilience.py
```

## Остановка после демонстрации

```bash
docker compose down
```

Для подробной инструкции проверки только ЛР7 см. [TESTING.md](TESTING.md).
