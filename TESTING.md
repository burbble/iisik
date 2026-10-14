# ЛР7: готовые команды для проверки

Запросы всех лабораторных на ЛР7: [LABS_DEMO.md](LABS_DEMO.md).

Все блоки ниже можно копировать целиком в Bash или Zsh. Токены и новые ID извлекаются автоматически; UUID, даты и пароли тестовых данных уже подставлены.

Проверяй одну лабораторную за раз: версии используют одинаковые порты. Запросы выполняй по порядку в одном терминале, чтобы сохранились функции и переменные.

## 1. Полный запуск через Docker Compose

Нужны Docker с Compose, `curl` и Python 3 для разбора ответов. `uv` и локальная установка зависимостей для Docker-режима не нужны. Из корня клонированного репозитория:

```bash
docker compose build
docker compose run --rm auth python -m app.scripts.seed
docker compose up -d --wait --wait-timeout 180
docker compose ps
```

`app.scripts.seed` сбрасывает демонстрационные базы этой лабораторной в `runtime-data`. Выполняй его перед первым прогоном и при необходимости повторить исходные данные, пока приложение остановлено. Контейнеры работают в фоне; запросы ниже можно выполнять в том же терминале.

Используется `apache/kafka:3.9.1`, настоящие Kafka, Redis и gRPC. Redis опубликован на `localhost:16379`, чтобы не конфликтовать с локальным Redis на `6379`; внутри Compose адрес остаётся `redis:6379`. Внешний порт можно изменить переменной `REDIS_PORT`.


## 2. Подготовка запросов и автоматический вход

Используется та же функция `login`, что и в `LABS_DEMO.md`: переменная `AUTH_API` не нужна. Скопируй целиком один раз в терминал из папки проекта. Функции выбирают HTTP с хоста или HTTP из контейнера `gateway`, если опубликованный порт отвечает таймаутом. Токен сохраняется автоматически.

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

Проверка HTTP изнутри Docker (не зависит от доступности опубликованного порта с хоста):

```bash
docker compose exec -T gateway python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5).read().decode())'
```

Для повторного входа скопируй `login admin`. Токен действует час.

### Текущий пользователь

Ожидается `admin@example.local`, роль `ADMIN`.

```bash
gql <<'JSON'
{"query": "{ me { id email roles } }"}
JSON
```

## 3. Просмотр тестовых данных

После свежего заполнения в базе два продукта за сентябрь 2026 года.

### Товары

Ожидаются товары `PD-1` и `DET-01`.

```bash
gql <<'JSON'
{"query": "{ products(filter:{active:true}) { id code name groupId unit active } }"}
JSON
```

### История производственного импорта

Есть завершённый импорт ERP за `2026-09-01`.

```bash
gql <<'JSON'
{"query": "{ importRuns(source:ERP, period:\"2026-09-01\") { id source period status recordsLoaded recordsFailed errors { errorCode message } } }"}
JSON
```

### Себестоимость первого продукта

До нового расчёта: `totalCost = 4000`, `unitCost = 40` (JSON может содержать строки с десятичными числами).

```bash
gql <<'JSON'
{"query": "{ costBreakdown(productId:\"22222222-2222-2222-2222-222222222222\",period:\"2026-09-01\") { calculationId productId version materialCost laborCost overheadCost totalCost producedQty unitCost } }"}
JSON
```

### Рентабельность

До пересчёта: прибыль первого продукта `3200`, второго `3150`.

```bash
gql <<'JSON'
{"query": "{ profitability(filter:{periodFrom:\"2026-09-01\",periodTo:\"2026-09-30\"}) { productId revenue costOfSales profit marginPercent } }"}
JSON
```

### Статус готового расчёта

Ожидается `COMPLETED`.

```bash
gql <<'JSON'
{"query": "{ calculationStatus(id:\"88888888-8888-8888-8888-888888888888\") { id status period productIds } }"}
JSON
```

### Фильтрация и сортировка

Вернутся подходящие товары, отсортированные по имени.

```bash
gql <<'JSON'
{"query": "{ products(filter:{active:true,search:\"П\"},sort:{field:NAME,direction:ASC}) { id code name } }"}
JSON
```

### Сводка рентабельности

До пересчёта: `count = 2`, `totalRevenue = 12400`, `totalCost = 6050`, `totalProfit = 6350`.

```bash
gql <<'JSON'
{"query": "{ profitabilitySummary(filter:{periodFrom:\"2026-09-01\",periodTo:\"2026-09-30\"}) { count totalRevenue totalCost totalProfit averageMarginPercent } }"}
JSON
```

## 4. Бизнес-операции

Эти запросы изменяют тестовые данные. Для повторения исходных результатов выполни `docker compose down`, снова заполни данные командой из раздела запуска и подними Compose. Повтор `retryImport` после успешного повтора уже вернёт ошибку состояния.

### Начать производственный импорт

Ожидается `COMPLETED`, `recordsLoaded = 0`: это демонстрационный сценарий, внешняя MES не опрашивается.

```bash
gql <<'JSON'
{"query": "mutation { startProductionImport(input:{source:MES,period:\"2026-10-01\"}) { id source period status recordsLoaded } }"}
JSON
```

### Начать финансовый импорт

Ожидается `COMPLETED`, `recordsLoaded = 0`.

```bash
gql <<'JSON'
{"query": "mutation { startFinancialImport(input:{source:FINANCE,period:\"2026-10-01\"}) { id source period status recordsLoaded } }"}
JSON
```

### Повторить заранее созданный неудачный импорт

Ожидается `COMPLETED`.

```bash
gql <<'JSON'
{"query": "mutation { retryImport(id:\"eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeef\") { id source period status } }"}
JSON
```

### Сопоставить внешний код продукта

Ожидается `RESOLVED` и внешний код `MES-DET-01`.

```bash
gql <<'JSON'
{"query": "mutation { resolveExternalMapping(input:{sourceSystem:\"MES\",entityType:\"PRODUCT\",externalCode:\"MES-DET-01\",internalId:\"33333333-3333-3333-3333-333333333333\"}) { id status externalCode internalId } }"}
JSON
```

### Пересчитать себестоимость двух продуктов

Создаются новые версии. Для `PD-1`: `totalCost = 4040`, `unitCost = 40.4`; для `DET-01`: `totalCost = 3760`, `unitCost = 18.8`.

```bash
gql <<'JSON'
{"query": "mutation { calculateCost(input:{period:\"2026-09-01\",productIds:[\"22222222-2222-2222-2222-222222222222\",\"33333333-3333-3333-3333-333333333333\"],allocationBase:\"LABOR_HOURS\"}) { calculationId productId version materialCost laborCost overheadCost totalCost unitCost } }"}
JSON
```


### Проверить автоматический расчёт через Kafka

Выполни после `calculateCost`, до явной Mutation рентабельности. Блок ждёт до 30 секунд и проверяет появление новых значений прибыли. Токен уже сохранён, ID и данные не нужно копировать. После свежего `seed` старые прибыли равны `3200` и `3150`, поэтому они не пройдут эту проверку.

```bash
docker compose exec -T -e DEMO_TOKEN="$TOKEN" gateway python - <<'PYTHON'
import json, os, time, urllib.request
query = '{ profitability(filter:{periodFrom:"2026-09-01",periodTo:"2026-09-30"}) { productId profit } }'
expected = {
    '22222222-2222-2222-2222-222222222222': 3168,
    '33333333-3333-3333-3333-333333333333': 3180,
}
for attempt in range(30):
    request = urllib.request.Request(
        'http://127.0.0.1:8000/graphql',
        data=json.dumps({'query': query}).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['DEMO_TOKEN']},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.load(response)
    if body.get('errors'):
        raise RuntimeError(body['errors'])
    found = {
        row['productId'] for row in body['data']['profitability']
        if row['productId'] in expected and float(row['profit']) == expected[row['productId']]
    }
    if found == set(expected):
        print('OK: Kafka автоматически запустила расчёт рентабельности')
        break
    time.sleep(1)
else:
    raise RuntimeError('Не получен автоматический результат: проверь логи analytics и Kafka')
PYTHON
```

Этот блок относится к полному Docker-режиму. В локальном режиме с памятью переходи сразу к явному расчёту ниже.

### Пересчитать рентабельность

Ожидается `COMPLETED`. В полном режиме Kafka уже запускает этот расчёт автоматически после себестоимости; запрос ниже позволяет дополнительно проверить явную Mutation.

```bash
gql <<'JSON'
{"query": "mutation { calculateProfitability(input:{period:\"2026-09-01\",productIds:[\"22222222-2222-2222-2222-222222222222\",\"33333333-3333-3333-3333-333333333333\"]}) { id status period productIds } }"}
JSON
```

### Посмотреть результат пересчёта

В результатах за сентябрь появятся расчёты с прибылью `3168` для `PD-1` и `3180` для `DET-01`. История старых расчётов может сохраняться.

```bash
gql <<'JSON'
{"query": "{ profitability(filter:{periodFrom:\"2026-09-01\",periodTo:\"2026-09-30\"}) { productId revenue costOfSales profit marginPercent } }"}
JSON
```

### Создать экспорт и автоматически проверить его статус

Новый ID извлекается из ответа. Ожидается `QUEUED`, `fileRef = null`: реализовано создание задания, а генератора файлов и endpoint скачивания в этом проекте нет.

```bash
EXPORT_RESPONSE=$(gql <<'JSON'
{"query": "mutation { exportReport(input:{format:XLSX}) { id status format fileRef } }"}
JSON
) && {
  printf '%s\n' "$EXPORT_RESPONSE"
  EXPORT_ID=$(printf '%s' "$EXPORT_RESPONSE" | python3 -c 'import json, sys; print(json.load(sys.stdin)["data"]["exportReport"]["id"])')
  gql <<JSON
{"query":"{ reportExport(id:\"$EXPORT_ID\") { id status format fileRef errorMessage } }"}
JSON
}
```

## 5. Проверка обработки ошибок

Это намеренно неуспешные запросы. Ожидается поле `errors`; функция `gql` вернёт ненулевой код.

### Пустой список продуктов

Ожидается ошибка `productIds cannot be empty`.

```bash
gql <<'JSON'
{"query": "mutation { calculateCost(input:{period:\"2026-09-01\",productIds:[],allocationBase:\"LABOR_HOURS\"}) { productId } }"}
JSON
```

### Недопустимый источник производственного импорта

Ожидается ошибка: производственный импорт допускает только ERP или MES. В ЛР6/7 сообщение может быть обёрнуто в ошибку gRPC.

```bash
gql <<'JSON'
{"query": "mutation { startProductionImport(input:{source:FINANCE,period:\"2026-10-01\"}) { id status } }"}
JSON
```

### Защищённый запрос без токена

Ожидается GraphQL-ошибка `Authentication required`.

```bash
SAVED_TOKEN="$TOKEN"
TOKEN=
gql <<'JSON'
{"query":"{ products { id code } }"}
JSON
TOKEN="$SAVED_TOKEN"
```

### Выход и проверка отозванного токена

Сначала `logout = true`, затем ответ об отказе для отозванного токена (HTTP `401`). Используется тот же транспорт, что и при входе.

```bash
gql <<'JSON'
{"query":"mutation { logout }"}
JSON
post_graphql <<'JSON'
{"query":"{ me { id } }"}
JSON
```

Чтобы снова выполнять запросы, скопируй `login admin` — функция уже определена.

## Автотесты в Docker

Команда выполняется из папки проекта. Тестовый контейнер не публикует порты; базы и заменители Kafka/Redis изолированы от запущенной системы.

```bash
docker compose run --rm --no-deps \
  -e LAB7_DATA_DIR=/tmp/lab-tests \
  -e LAB7_EVENT_BACKEND=memory \
  -e LAB7_SESSION_BACKEND=memory \
  -e LAB7_CACHE_BACKEND=memory \
  auth python -m pytest -q
```

## Остановка Docker-приложения

После завершения запросов:

```bash
docker compose down
```

## Дополнительный локальный режим без Kafka/Redis

Этот вариант нужен, если требуется только проверка API без Docker. Нужны Python 3.11+ и `uv`. Останови Compose: локальные сервисы используют те же HTTP/gRPC-порты. Из папки проекта:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m app.scripts.seed
```

Здесь `seed` сбрасывает локальные базы в `.data`, а не базы Docker в `runtime-data`. HTTP и gRPC настоящие; Kafka, Redis-сессии и кеш заменяются памятью. События между процессами не доставляются: после `calculateCost` обязательно выполни `calculateProfitability`.

```bash
bash <<'BASH'
export LAB7_EVENT_BACKEND=memory
export LAB7_SESSION_BACKEND=memory
export LAB7_CACHE_BACKEND=memory
export AUTH_SERVICE_URL=http://127.0.0.1:8001
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true; wait 2>/dev/null || true' EXIT
for service in master_data production financial costing analytics reporting; do
  .venv/bin/python -m app.transport.grpc.server "$service" &
  pids+=("$!")
done
.venv/bin/uvicorn app.services.auth.api:app --host 127.0.0.1 --port 8001 &
pids+=("$!")
.venv/bin/uvicorn app.gateway.main:app --host 127.0.0.1 --port 8000 &
pids+=("$!")
wait
BASH
```

Запуск занимает первый терминал. Запросы из разделов 2–5 копируй во второй. `Ctrl+C` останавливает локальные сервисы.

Исходные GraphQL-примеры: [docs/graphql_examples.graphql](docs/graphql_examples.graphql).

## Если localhost отвечает таймаутом

Сначала проверь состояние контейнеров и HTTP изнутри Docker:

```bash
docker compose ps
docker compose logs --tail 50 gateway analytics reporting
docker compose exec -T gateway python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5).read().decode())'
```

Если внутренняя проверка возвращает `status: ok`, а `curl` с хоста зависает, это отдельная проблема доступа из хоста к контейнерам. Проверь настройки VPN/файрвола и проброс портов.
