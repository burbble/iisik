# ЛР2: проверка технического проекта

В этой лабораторной нет запущенного приложения и HTTP API: здесь SQL, GraphQL- и protobuf-контракты, примеры Kafka-событий. Рабочие запросы находятся в `TESTING.md` ЛР3, ЛР4, ЛР6 и ЛР7.

## Проверить контракты одной командой

Из общей папки `iisik` перейди в проект:

```bash
cd './ЛР2_анализ_рентабельности_технический_проект/lab2_profitability_project'
```

Нужны Python 3.11+ и `uv`. Команда временно подключает инструменты проверки, не создаёт серверы и не меняет данные. Проверяет GraphQL-схему, Kafka envelope по JSON Schema и компиляцию protobuf. SQLite используется только для проверки базового синтаксиса SQL и создания таблиц; это не полноценная проверка семантики PostgreSQL.

```bash
uv run --no-project --with graphql-core --with jsonschema --with grpcio-tools python - <<'PYTHON'
import json
import sqlite3
import tempfile
from pathlib import Path
from graphql import build_schema, validate_schema
from jsonschema import Draft202012Validator, FormatChecker
from grpc_tools import protoc

schema = build_schema(Path('graphql/schema.graphql').read_text())
errors = validate_schema(schema)
assert not errors, errors
print('OK: GraphQL schema')

validator = Draft202012Validator(
    json.loads(Path('kafka/event-envelope.schema.json').read_text()),
    format_checker=FormatChecker(),
)
for path in sorted(Path('kafka/examples').glob('*.json')):
    validator.validate(json.loads(path.read_text()))
    print('OK:', path)

for path in sorted(Path('sql').glob('*.sql')):
    with sqlite3.connect(':memory:') as db:
        db.executescript(path.read_text())
        count = db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        print('OK:', path, 'tables:', count)

with tempfile.TemporaryDirectory() as output:
    result = protoc.main(['protoc', '-Iproto', f'--python_out={output}', 'proto/profitability.proto'])
    assert result == 0, 'Protobuf compilation failed'
print('OK: Protobuf contract')
print('Все перечисленные проверки прошли')
PYTHON
```
