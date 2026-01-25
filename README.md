# Radio-T Data

Данные и инструменты для анализа транскриптов подкаста [Радио-Т](https://radio-t.com/).

## Структура репозитория

```
├── data_clean/              # Очищенные транскрипты (992 эпизода)
│   └── {N}/
│       └── {N}_cc.json      # Транскрипт с разметкой спикеров
├── cleaning/                # Система очистки данных
│   ├── clean.py             # Скрипт применения правил очистки
│   ├── people.yaml          # Справочник участников подкаста
│   └── configs/             # YAML конфиги с правилами
├── validation/              # Результаты валидации спикеров
│   └── episodes/
│       └── 0000-0099/       # Батчи по 100 эпизодов
│           └── 0001.yaml    # Результат анализа эпизода
├── scripts/
│   ├── run_claude.py        # Запуск Claude для анализа эпизодов
│   └── preprocess_stats.py  # Предрасчёт статистики спикеров
└── requirements.txt
```

## Установка

### 1. Клонирование репозитория

```bash
git clone git@github.com:ufian/radio-t-data.git
cd radio-t-data
```

### 2. Создание Python окружения

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# или
.venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Установка Claude Code

Для работы `run_claude.py` требуется [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code):

```bash
npm install -g @anthropic-ai/claude-code
```

## Использование

### Запуск анализа эпизодов

```bash
# Один эпизод
.venv/bin/python scripts/run_claude.py 307

# Диапазон эпизодов
.venv/bin/python scripts/run_claude.py 0-99

# Несколько конкретных эпизодов
.venv/bin/python scripts/run_claude.py 100 200 300

# Показать промпт без запуска (dry-run)
.venv/bin/python scripts/run_claude.py --dry-run 307

# Принудительно переобработать уже готовые
.venv/bin/python scripts/run_claude.py --no-skip 307
```

### Параметры run_claude.py

| Параметр | Описание |
|----------|----------|
| `episodes` | Номера эпизодов или диапазоны (обязательный) |
| `--dry-run` | Показать промпт без запуска Claude |
| `--no-skip` | Не пропускать уже обработанные эпизоды |
| `--data-dir PATH` | Путь к директории с данными |

### Примеры

```bash
# Обработать первые 100 эпизодов (пропустит уже готовые)
.venv/bin/python scripts/run_claude.py 0-99

# Проверить что будет проанализировано для эпизода 62
.venv/bin/python scripts/run_claude.py --dry-run 62
```

### Результаты

Результаты сохраняются в `validation/episodes/{batch}/{episode}.yaml`:

```yaml
episode: 62
status: clean  # clean | needs_review | has_tasks
analyzed_at: "2024-01-24"

speakers_summary:
  hosts_present: [Umputun]
  total_duration_sec: 4376.8

unknown_speakers:
  - speaker: "Guest1"
    identified_as: "gimlis"
    confidence: high
    evidence: "Представлен как Гимлес в 32.4s"

suggested_rules:
  - type: rename
    from_speaker: "Guest1"
    to_speaker: "Gimlis"
```

## Очистка данных

Применение правил очистки к исходным данным:

```bash
# Применить все правила
.venv/bin/python cleaning/clean.py

# Только определённые эпизоды
.venv/bin/python cleaning/clean.py --episodes 300-350

# Dry-run (без сохранения)
.venv/bin/python cleaning/clean.py --dry-run
```

## Время обработки

- Среднее время на эпизод: ~54 секунды
- 100 эпизодов: ~90 минут
- Все 992 эпизода: ~15 часов

При достижении rate limit скрипт остановится. Повторный запуск автоматически продолжит с места остановки.

## Лицензия

MIT
