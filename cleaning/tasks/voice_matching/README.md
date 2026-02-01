# Voice Matching Tasks

Задания для идентификации спикеров через сравнение голосовых эмбеддингов.

## Requirements

**Python 3.11** (обязательно — PyTorch/torchaudio не поддерживают 3.13+)

### Создание виртуального окружения

```bash
# macOS (Homebrew)
brew install python@3.11

# Создать venv
python3.11 -m venv .venv

# Активировать
source .venv/bin/activate

# Проверить версию
python --version  # Python 3.11.x
```

### Установка зависимостей

```bash
# Базовые зависимости
pip install torch 'torchaudio>=2.0.0,<2.5.0' numpy scipy soundfile pyyaml requests tqdm

# Speaker embedding модели
pip install pyannote.audio speechbrain

# TitaNet (опционально, ~2GB)
pip install nemo_toolkit[asr]
```

**Важно:** torchaudio 2.10+ несовместим со speechbrain (удалён `list_audio_backends()`). Используйте `torchaudio < 2.5`.

## Структура

```
voice_matching/
├── README.md                    # Этот файл
├── episodes/                    # Задания для отдельных эпизодов
│   ├── 0100.yaml
│   ├── 0309.yaml
│   └── ...
├── cross_episode_tasks.yaml     # Сравнение одного имени между эпизодами
├── batches.yaml                 # Агрегация по диапазонам (только episode tasks)
├── batches/                     # Детальные batch-файлы (только episode tasks)
│   ├── 0000-0099.yaml
│   └── ...
└── unified_batches/             # ОБЪЕДИНЁННЫЕ batch-файлы (рекомендуется)
    ├── summary.yaml             # Сводка по всем batch'ам
    ├── 0000-0099.yaml           # Все сегменты для эпизодов 0-99
    ├── 0100-0199.yaml
    └── ...
```

## Рекомендуемый workflow: unified_batches/

Папка `unified_batches/` содержит **объединённые** задания — для каждого эпизода собраны ВСЕ сегменты из всех источников:
- Episode identification (unknown + reference speakers)
- Cross-episode comparison (same name verification)

Это позволяет:
1. **Вырезать аудио один раз** для каждого эпизода
2. **Посчитать эмбеддинги** для всех сегментов сразу
3. **Использовать эмбеддинги** для разных целей анализа

### Unified Batches Summary

| Batch | Эпизодов | Сегментов | Длительность |
|-------|----------|-----------|--------------|
| 0000-0099 | 7 | 10 | 13.6 min |
| 0100-0199 | 4 | 19 | 17.8 min |
| 0200-0299 | 14 | 58 | 55.6 min |
| 0300-0399 | 19 | 154 | 135.6 min |
| 0400-0499 | 17 | 107 | 99.4 min |
| 0500-0599 | 9 | 70 | 77.8 min |
| 0600-0699 | 8 | 58 | 68.1 min |
| 0900-0999 | 2 | 7 | 9.5 min |

**Всего: 80 эпизодов, 483 сегмента, 477 минут аудио**

## Типы заданий

### 1. Episode Tasks (`episodes/*.yaml`)

Идентификация неизвестных спикеров внутри одного эпизода.

**Формат файла:**
```yaml
episode: 309
unknown_speakers:
  - speaker: SPEAKER_00
    total_time: 849.1     # Общее время речи (сек)
    segments:             # Лучшие сегменты для извлечения
      - stime: 1910.57
        etime: 1960.94
        text: "Не, подожди, Жень, смотри..."
        duration: 50.37

reference_speakers:       # Известные спикеры для сравнения
  - speaker: Umputun
    total_time: 3862.1
    reference_segment:
      stime: 715.25
      etime: 800.61

segments_to_extract:      # Все сегменты для извлечения аудио
  - speaker: SPEAKER_00
    stime: 925.41
    etime: 962.56
    type: unknown
  - speaker: Umputun
    stime: 715.25
    etime: 800.61
    type: reference

comparisons:              # Что с чем сравнивать
  - unknown: SPEAKER_00
    compare_with: [Bobuk, Marin_k_a, Umputun]
```

### 2. Cross-Episode Tasks (`cross_episode_tasks.yaml`)

Проверка того, что спикер с простым именем (Alex, Andrey) — один и тот же человек в разных эпизодах.

**Спикеры для проверки:**
- Alex (5 эпизодов: 2, 5, 6, 17, 18)
- Alexander (3 эпизода: 27, 243, 524)
- Grinch (2 эпизода: 193, 196)
- Mika (2 эпизода: 209, 211)
- Lena (3 эпизода: 234, 239, 247)
- Ruslan (5 эпизодов: 299, 327, 425, 465, 536)
- Dmitry (2 эпизода: 441, 517)
- Andrey (2 эпизода: 486, 976)

### 3. Batch Tasks (`batches/`)

Агрегация по диапазонам эпизодов для параллельной обработки.

| Batch | Эпизодов | Сегментов |
|-------|----------|-----------|
| 0000-0099 | 1 | 4 |
| 0100-0199 | 2 | 17 |
| 0200-0299 | 7 | 51 |
| 0300-0399 | 18 | 153 |
| 0400-0499 | 14 | 104 |
| 0500-0599 | 7 | 68 |
| 0600-0699 | 8 | 58 |
| 0900-0999 | 1 | 6 |

**Всего: 58 эпизодов, 461 сегмент**

### Примечание

Эпизоды 855, 856 не включены — у SPEAKER_01/02 там только короткие реплики (< 4 сек), непригодные для voice matching. Требуют ручного review.

## Запуск process_voice_batch.py

Основной скрипт для извлечения аудио-сегментов и вычисления voice embeddings.

### Использование

```bash
# Обработать batch (скачивание + извлечение + эмбеддинги)
.venv/bin/python scripts/process_voice_batch.py --batch 0300-0399

# Только один эпизод из batch
.venv/bin/python scripts/process_voice_batch.py --batch 0900-0999 --episode 994

# Пропустить скачивание (если аудио уже в cache/)
.venv/bin/python scripts/process_voice_batch.py --batch 0900-0999 --skip-download

# Выбрать конкретные модели
.venv/bin/python scripts/process_voice_batch.py --batch 0900-0999 --models pyannote,ecapa,titanet
```

### Доступные модели

| Модель | Размерность | Описание |
|--------|-------------|----------|
| `pyannote` | 512 | pyannote/embedding — лёгкая, быстрая |
| `ecapa` | 192 | speechbrain ECAPA-TDNN — хорошее качество |
| `titanet` | 192 | NVIDIA TitaNet-Large — state-of-the-art |

По умолчанию используется только `pyannote`. Для лучших результатов рекомендуется `--models pyannote,ecapa,titanet`.

### Структура результатов

```
results/
└── 0900-0999/
    ├── segments/                    # Извлечённые аудио-сегменты
    │   └── 994_Umputun_5782.1.wav
    └── embeddings/
        ├── pyannote/
        │   └── 994_Umputun_5782.1.npy
        ├── ecapa/
        │   └── 994_Umputun_5782.1.npy
        └── titanet/
            └── 994_Umputun_5782.1.npy
```

### Кэширование аудио

Скрипт скачивает MP3 эпизодов в `cache/` директорию:
- `cache/rt_podcast994.mp3`
- Используйте `--skip-download` если файлы уже скачаны

### Пример полного workflow

```bash
# 1. Обработать все batch'и (параллельно)
for batch in 0000-0099 0100-0199 0200-0299 0300-0399 0400-0499 0500-0599 0600-0699 0900-0999; do
    .venv/bin/python scripts/process_voice_batch.py --batch $batch --models pyannote,ecapa,titanet &
done
wait

# 2. Анализ результатов (TODO)
.venv/bin/python scripts/analyze_embeddings.py --batch 0300-0399
```

## Альтернативный процесс (устаревший)

### Шаг 1: Извлечение аудио-сегментов

```bash
# Для каждого batch извлечь ВСЕ сегменты из unified_batches
python scripts/extract_audio_segments.py --unified-batch 0300-0399

# Или для всех batch'ей параллельно
for batch in 0000-0099 0100-0199 0200-0299 0300-0399 0400-0499 0500-0599 0600-0699 0900-0999; do
    python scripts/extract_audio_segments.py --unified-batch $batch &
done
```

### Шаг 2: Вычисление эмбеддингов

```bash
# Использовать pyannote-audio или похожий инструмент
python scripts/compute_embeddings.py --unified-batch 0300-0399
```

### Шаг 3: Анализ результатов

```bash
# Episode identification: сравнить unknown с reference
python scripts/analyze_episode_embeddings.py --batch 0300-0399

# Cross-episode comparison: сравнить сегменты с одинаковым comparison_group
python scripts/analyze_cross_episode.py --group Grinch
```

### Шаг 4: Применение результатов

```bash
# Обновить конфиги очистки с идентифицированными спикерами
python scripts/apply_voice_results.py
```

## Критерии сегментов

- **Минимальная длительность сегмента:** 10 секунд
- **Целевая длительность:** 30 секунд
- **Минимальное общее время речи:** 60 секунд
- **Максимум сегментов на спикера:** 3 лучших

## Статистика

### Episode tasks (episodes/)
- 58 эпизодов с неизвестными спикерами
- 461 сегмент

### Cross-episode tasks
- 8 спикеров для проверки между эпизодами
- 22 сегмента

### Unified batches (рекомендуется)
- 80 эпизодов (объединение всех задач)
- 483 сегмента
- 477 минут аудио для извлечения
