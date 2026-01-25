#!/usr/bin/env python3
"""
Запуск Claude для обработки эпизодов подкаста Радио-Т

Использование:
    python scripts/run_claude.py 307              # Один эпизод
    python scripts/run_claude.py 300-350          # Диапазон эпизодов
    python scripts/run_claude.py 100 200 300      # Несколько конкретных эпизодов
    python scripts/run_claude.py --dry-run 307    # Показать промпт без запуска
"""

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

# Маркеры rate limit в выводе Claude
RATE_LIMIT_MARKERS = [
    "rate limit",
    "quota exceeded",
    "too many requests",
    "resource_exhausted",
    "rate_limit_error",
]

# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_RATE_LIMIT = 2


# ==============================================================================
# PREPROCESSING - статистика спикеров
# ==============================================================================

KNOWN_HOSTS = {'Umputun', 'Bobuk', 'Gray', 'Ksenks', 'Alek.sys'}
SPECIAL_SPEAKERS = {'SPEAKER_99', '_ad'}


def calculate_speaker_stats(cc_file: Path) -> dict:
    """Рассчитывает статистику спикеров для эпизода."""
    with open(cc_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    subs = data.get('subs', [])
    stats = defaultdict(lambda: {
        'replies_count': 0,
        'total_duration_sec': 0.0,
        'first_time_sec': None,
        'sample_texts': [],
    })

    for sub in subs:
        author = sub.get('author', 'UNKNOWN')
        duration = sub.get('etime', 0) - sub.get('stime', 0)

        stats[author]['replies_count'] += 1
        stats[author]['total_duration_sec'] += duration

        if stats[author]['first_time_sec'] is None:
            stats[author]['first_time_sec'] = sub.get('stime', 0)

        if len(stats[author]['sample_texts']) < 3:
            text = sub.get('text', '')[:80]
            if text:
                stats[author]['sample_texts'].append(f"{sub.get('stime', 0):.1f}s: {text}")

    # Форматируем результат
    hosts = []
    unknown = []

    for speaker, s in stats.items():
        if speaker in SPECIAL_SPEAKERS:
            continue

        entry = f"- **{speaker}**: {s['replies_count']} реплик, {s['total_duration_sec']:.0f} сек"
        if s['first_time_sec'] is not None:
            entry += f", первая в {s['first_time_sec']:.0f}s"

        if speaker in KNOWN_HOSTS:
            hosts.append((s['total_duration_sec'], entry))
        else:
            samples = "; ".join(s['sample_texts'][:2])
            unknown.append((s['total_duration_sec'], f"{entry}\n  Примеры: {samples}"))

    hosts.sort(reverse=True)
    unknown.sort(reverse=True)

    return {
        'hosts': [h[1] for h in hosts],
        'unknown': [u[1] for u in unknown],
    }


# ==============================================================================
# PROMPT TEMPLATE - редактируйте здесь
# ==============================================================================

def get_prompt(episode: int, cc_file: Path, desc_file: Path, chat_file: Path) -> str:
    """
    Формирует промпт для Claude.

    Аргументы:
        episode: номер эпизода
        cc_file: путь к файлу с транскриптом
        desc_file: путь к файлу с метаданными
        chat_file: путь к файлу с чатом
    """
    project_dir = cc_file.parent.parent.parent
    people_file = project_dir / 'cleaning' / 'people.yaml'

    # Определяем папку для результата
    batch_start = (episode // 100) * 100
    batch_end = batch_start + 99
    batch_folder = f"{batch_start:04d}-{batch_end:04d}"
    output_file = project_dir / 'validation' / 'episodes' / batch_folder / f'{episode:04d}.yaml'

    # Предрассчитанная статистика
    stats = calculate_speaker_stats(cc_file)
    hosts_stats = "\n".join(stats['hosts']) if stats['hosts'] else "Нет данных"
    unknown_stats = "\n".join(stats['unknown']) if stats['unknown'] else "Нет неизвестных спикеров"

    return f"""# Задача: Валидация спикеров эпизода {episode} подкаста Радио-Т

## Контекст

Ты анализируешь транскрипт подкаста для выявления ошибок разметки спикеров.

**Файлы для анализа:**
- Транскрипт: {cc_file}
- Метаданные: {desc_file}
- Справочник участников: {people_file}

**Известные ведущие:** Umputun, Bobuk, Gray, Ksenks, Alek.sys

**Неизвестные спикеры (требуют анализа):**
- `SPEAKER_00` - `SPEAKER_08` — автоматическая разметка
- `Guest`, `Guest1`-`Guest29` — старые неидентифицированные гости
- `SPEAKER_MISATTRIBUTED_*` — отменённые ошибочные присвоения

**Специальные спикеры (игнорировать):**
- `SPEAKER_99` — аудио-артефакты, джинглы
- `_ad` — реклама

## Предрассчитанная статистика

### Ведущие в этом эпизоде:
{hosts_stats}

### Неизвестные спикеры:
{unknown_stats}

## Алгоритм анализа

### Шаг 1: Анализ статистики (УЖЕ ПОСЧИТАНО ВЫШЕ)

Статистика уже посчитана. Используй её для принятия решений.

### Шаг 2: Анализ неизвестных спикеров

Для каждого неизвестного спикера определи:

**2.1. Это ошибка распознавания?**
- Короткие реплики (<5 сек) в случайные моменты → скорее всего ошибка
- Типичные фразы-ошибки: "Хорошо", "Да", "Нет", "Угу", односложные реакции

**2.2. Это реальный гость?**
- Несколько реплик подряд с осмысленным содержанием
- Суммарная длительность >60 сек
- Участие в диалоге (вопросы-ответы)

### Шаг 3: Идентификация гостей

Для реальных гостей попробуй определить кто это:

**3.1. Поиск представления**
- Проверь первые 10 минут подкаста — часто там представляют гостей
- Проверь контекст вокруг первой реплики гостя
- Ищи фразы: "у нас в гостях", "с нами сегодня", "представляю", обращения по имени

**3.2. Анализ контекста**
- Мог ли это быть один из ведущих (плохо распознанный)?
- Есть ли характерные темы/экспертиза, указывающие на конкретного человека?
- Сверься со справочником гостей в {people_file}

**3.3. Оценка уверенности**
- high (>80%): явное представление или очевидный контекст
- medium (50-80%): косвенные признаки
- low (<50%): только предположение

### Шаг 4: Подготовка заданий

Если идентифицировать не удалось, подготовь задание для voice comparison:

**4.1. Найди референсные фразы:**
- Для неизвестного спикера: самая длинная непрерывная речь (без перебивок)
- Минимум 10 секунд, желательно 20-30 сек

**4.2. Запиши таймстемпы:**
- stime и etime для каждого сегмента
- URL аудио из метаданных

### Шаг 5: Проверка консистентности

Для ВСЕХ спикеров (включая ведущих):
- Был ли спикер представлен/упомянут в начале?
- Если нет — насколько много он говорил?
- Может ли это быть ошибкой распознавания другого ведущего?

## Формат вывода

Создай файл: {output_file}

```yaml
episode: {episode}
status: clean | needs_review | has_tasks
analyzed_at: "<текущая дата ISO>"

# Статистика по всем спикерам
speakers_summary:
  hosts_present: [список ведущих в этом выпуске]
  total_duration_sec: <общая длительность>

# Детальный анализ неизвестных спикеров
unknown_speakers:
  - speaker: "<имя спикера>"
    total_duration_sec: <число>
    replies_count: <число>
    pattern: scattered | consecutive

    # Результат анализа
    analysis:
      is_error: true | false
      error_reason: "<почему считаем ошибкой>" | null

      # Если не ошибка - попытка идентификации
      identified_as: "<person_id из people.yaml>" | null
      identification_method: "introduction" | "context" | null
      confidence: high | medium | low | null
      evidence: "<цитата или описание>" | null

      # Если не удалось идентифицировать
      possible_matches:
        - person_id: "<id>"
          confidence: <0.0-1.0>
          reason: "<почему>"

      # Задание на voice comparison (если нужно)
      voice_task:
        needed: true | false
        reference_segment:
          stime: <число>
          etime: <число>
          text: "<текст фразы>"

# Проверка консистентности
consistency_check:
  all_speakers_introduced: true | false
  issues:
    - speaker: "<имя>"
      issue: "<описание проблемы>"

# Предлагаемые правила очистки (если есть явные ошибки)
suggested_rules:
  - type: rename
    episode: {episode}
    from_speaker: "<старое имя>"
    to_speaker: "<новое имя>"
    confidence: high | medium
    reason: "<обоснование>"
```

## Важно

1. ОБЯЗАТЕЛЬНО создай директорию и файл результата:
   ```bash
   mkdir -p {output_file.parent}
   ```
   Затем создай файл {output_file} с результатами анализа.

2. НЕ создавай файл если не можешь его полностью заполнить
3. Будь консервативен: лучше пометить "needs_review" чем ошибиться
4. Для voice_task выбирай сегменты с чистой речью (без смеха, перебивок)

Начни анализ. После анализа ОБЯЗАТЕЛЬНО запиши результат в файл.
"""


# ==============================================================================
# Основная логика
# ==============================================================================

def parse_episodes(args: list[str]) -> list[int]:
    """Парсит аргументы в список эпизодов."""
    episodes = []

    for arg in args:
        if '-' in arg:
            # Диапазон: 300-350
            start, end = arg.split('-', 1)
            start = int(start) if start else 0
            end = int(end) if end else 999
            episodes.extend(range(start, end + 1))
        else:
            # Конкретный эпизод
            episodes.append(int(arg))

    return sorted(set(episodes))


def run_claude(prompt: str, dry_run: bool = False) -> tuple[int, bool]:
    """
    Запускает Claude с промптом.

    Returns:
        (exit_code, hit_rate_limit)
    """
    if dry_run:
        print("=== PROMPT ===")
        print(prompt)
        print("=== END PROMPT ===")
        return 0, False

    result = subprocess.run(
        ['claude', '-p', prompt, '--permission-mode', 'bypassPermissions'],
        capture_output=True,
        text=True
    )

    # Выводим результат
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Проверяем rate limit
    output = (result.stdout + result.stderr).lower()
    hit_limit = any(marker in output for marker in RATE_LIMIT_MARKERS)

    return result.returncode, hit_limit


def get_output_path(episode: int, project_dir: Path) -> Path:
    """Возвращает путь к файлу результата для эпизода."""
    batch_start = (episode // 100) * 100
    batch_end = batch_start + 99
    batch_folder = f"{batch_start:04d}-{batch_end:04d}"
    return project_dir / 'validation' / 'episodes' / batch_folder / f'{episode:04d}.yaml'


def main():
    parser = argparse.ArgumentParser(
        description='Запуск Claude для обработки эпизодов подкаста',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'episodes',
        nargs='+',
        help='Номера эпизодов (307) или диапазоны (300-350)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Показать промпт без запуска Claude'
    )
    parser.add_argument(
        '--no-skip',
        action='store_true',
        help='Не пропускать уже обработанные эпизоды (по умолчанию пропускаются)'
    )
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=None,
        help='Путь к директории с данными (по умолчанию: data_clean)'
    )

    args = parser.parse_args()

    # Определяем пути
    script_path = Path(__file__).resolve()
    project_dir = script_path.parent.parent
    data_dir = args.data_dir or (project_dir / 'data_clean')

    if not data_dir.exists():
        print(f"Ошибка: директория {data_dir} не существует")
        sys.exit(EXIT_ERROR)

    # Парсим эпизоды
    episodes = parse_episodes(args.episodes)
    print(f"Эпизодов в запросе: {len(episodes)}")

    # Фильтруем уже обработанные
    skip_existing = not args.no_skip
    if skip_existing and not args.dry_run:
        original_count = len(episodes)
        episodes = [
            ep for ep in episodes
            if not get_output_path(ep, project_dir).exists()
        ]
        skipped = original_count - len(episodes)
        if skipped > 0:
            print(f"Пропущено (уже обработаны): {skipped}")

    print(f"Эпизодов для обработки: {len(episodes)}")
    print()

    if not episodes:
        print("Нет эпизодов для обработки.")
        sys.exit(EXIT_SUCCESS)

    # Счётчики
    processed = 0
    errors = 0
    total_time = 0.0

    # Обрабатываем каждый эпизод
    for episode in episodes:
        cc_file = data_dir / str(episode) / f'{episode}_cc.json'
        desc_file = data_dir / str(episode) / f'{episode}_desc.json'
        chat_file = data_dir / str(episode) / f'{episode}_chat.json'

        if not cc_file.exists():
            print(f"Эпизод {episode}: файл {cc_file} не найден, пропускаем")
            continue

        print(f"=== Эпизод {episode} ===")

        prompt = get_prompt(episode, cc_file, desc_file, chat_file)

        start_time = time.time()
        returncode, hit_limit = run_claude(prompt, dry_run=args.dry_run)
        elapsed = time.time() - start_time
        total_time += elapsed

        if hit_limit:
            print()
            print("=" * 60)
            print("RATE LIMIT REACHED")
            print(f"Последний обработанный эпизод: {episode}")
            print(f"Обработано в этом запуске: {processed}")
            print()
            print("Для продолжения просто запустите скрипт снова с теми же параметрами.")
            print("Уже обработанные эпизоды будут автоматически пропущены.")
            print("=" * 60)
            sys.exit(EXIT_RATE_LIMIT)

        if returncode != 0:
            print(f"Эпизод {episode}: Claude завершился с кодом {returncode}")
            errors += 1
        else:
            processed += 1

        print(f"Эпизод {episode} завершён за {elapsed:.1f} сек")
        print()

    print("=" * 60)
    print("ГОТОВО")
    print(f"Обработано: {processed}")
    if errors > 0:
        print(f"Ошибок: {errors}")
    print(f"Общее время: {total_time:.1f} сек")
    if processed > 0:
        avg_time = total_time / processed
        print(f"Среднее время на эпизод: {avg_time:.1f} сек")
        remaining = len(episodes) - processed
        if remaining > 0:
            print(f"Осталось эпизодов: {remaining}, примерно {remaining * avg_time / 60:.0f} мин")
    print("=" * 60)

    sys.exit(EXIT_SUCCESS if errors == 0 else EXIT_ERROR)


if __name__ == '__main__':
    main()
