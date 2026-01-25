#!/usr/bin/env python3
"""
Предварительный расчёт статистики спикеров для эпизодов.

Создаёт JSON файл со статистикой, который можно передать в промпт для Claude,
чтобы не тратить время на парсинг и подсчёт.

Использование:
    python scripts/preprocess_stats.py 62           # Один эпизод
    python scripts/preprocess_stats.py 0-99         # Диапазон
    python scripts/preprocess_stats.py --all        # Все эпизоды
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Известные ведущие
KNOWN_HOSTS = {'Umputun', 'Bobuk', 'Gray', 'Ksenks', 'Alek.sys'}

# Специальные спикеры (игнорировать)
SPECIAL_SPEAKERS = {'SPEAKER_99', '_ad'}

# Паттерны неизвестных спикеров
UNKNOWN_PATTERNS = [
    'SPEAKER_',
    'SPEAKER_MISATTRIBUTED_',
    'Guest',
]


def is_unknown_speaker(name: str) -> bool:
    """Проверяет, является ли спикер неизвестным."""
    if name in KNOWN_HOSTS:
        return False
    if name in SPECIAL_SPEAKERS:
        return False
    for pattern in UNKNOWN_PATTERNS:
        if name.startswith(pattern):
            return True
    return False


def analyze_pattern(subs: list[dict], author: str) -> str:
    """
    Определяет паттерн появления спикера.

    - scattered: разрозненные короткие реплики
    - consecutive: последовательные осмысленные реплики
    """
    author_subs = [s for s in subs if s.get('author') == author]
    if not author_subs:
        return 'none'

    # Считаем количество "блоков" последовательных реплик
    blocks = []
    current_block = []

    for i, sub in enumerate(author_subs):
        if not current_block:
            current_block = [sub]
        else:
            # Проверяем, близко ли к предыдущей реплике этого автора
            prev_sub = current_block[-1]
            gap = sub['stime'] - prev_sub['etime']

            # Если gap < 30 сек — это часть одного блока
            if gap < 30:
                current_block.append(sub)
            else:
                blocks.append(current_block)
                current_block = [sub]

    if current_block:
        blocks.append(current_block)

    # Анализируем блоки
    long_blocks = [b for b in blocks if len(b) >= 3]

    if long_blocks:
        return 'consecutive'
    elif len(blocks) > 5 and all(len(b) <= 2 for b in blocks):
        return 'scattered'
    else:
        return 'mixed'


def get_speaker_stats(subs: list[dict]) -> dict[str, Any]:
    """Собирает статистику по спикерам."""
    stats = defaultdict(lambda: {
        'replies_count': 0,
        'total_duration_sec': 0.0,
        'first_time_sec': None,
        'last_time_sec': None,
        'sample_texts': [],
    })

    for sub in subs:
        author = sub.get('author', 'UNKNOWN')
        duration = sub.get('etime', 0) - sub.get('stime', 0)

        stats[author]['replies_count'] += 1
        stats[author]['total_duration_sec'] += duration

        if stats[author]['first_time_sec'] is None:
            stats[author]['first_time_sec'] = sub.get('stime', 0)
        stats[author]['last_time_sec'] = sub.get('etime', 0)

        # Сохраняем примеры текста (первые 5)
        if len(stats[author]['sample_texts']) < 5:
            text = sub.get('text', '')[:100]
            if text:
                stats[author]['sample_texts'].append({
                    'text': text,
                    'stime': sub.get('stime', 0),
                })

    return dict(stats)


def process_episode(episode: int, data_dir: Path) -> dict[str, Any] | None:
    """Обрабатывает один эпизод."""
    cc_file = data_dir / str(episode) / f'{episode}_cc.json'

    if not cc_file.exists():
        return None

    with open(cc_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    subs = data.get('subs', [])
    if not subs:
        return None

    speaker_stats = get_speaker_stats(subs)

    # Классифицируем спикеров
    hosts = []
    unknown = []
    special = []

    for speaker, stats in speaker_stats.items():
        stats['pattern'] = analyze_pattern(subs, speaker)
        stats['total_duration_sec'] = round(stats['total_duration_sec'], 1)

        if speaker in KNOWN_HOSTS:
            hosts.append({'name': speaker, **stats})
        elif speaker in SPECIAL_SPEAKERS:
            special.append({'name': speaker, **stats})
        elif is_unknown_speaker(speaker):
            unknown.append({'name': speaker, **stats})
        else:
            # Другие спикеры (возможно известные гости)
            unknown.append({'name': speaker, **stats})

    # Сортируем по длительности
    hosts.sort(key=lambda x: -x['total_duration_sec'])
    unknown.sort(key=lambda x: -x['total_duration_sec'])

    total_duration = sum(s.get('etime', 0) - s.get('stime', 0) for s in subs)

    return {
        'episode': episode,
        'total_duration_sec': round(total_duration, 1),
        'total_replies': len(subs),
        'hosts': hosts,
        'unknown_speakers': unknown,
        'special_speakers': special,
        'has_unknown': len(unknown) > 0,
    }


def parse_episodes(args: list[str], data_dir: Path) -> list[int]:
    """Парсит аргументы в список эпизодов."""
    episodes = []

    for arg in args:
        if '-' in arg:
            start, end = arg.split('-', 1)
            start = int(start) if start else 0
            end = int(end) if end else 999
            episodes.extend(range(start, end + 1))
        else:
            episodes.append(int(arg))

    # Фильтруем существующие
    existing = []
    for ep in episodes:
        if (data_dir / str(ep)).exists():
            existing.append(ep)

    return sorted(set(existing))


def main():
    parser = argparse.ArgumentParser(
        description='Предварительный расчёт статистики спикеров',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'episodes',
        nargs='*',
        help='Номера эпизодов или диапазоны'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Обработать все эпизоды'
    )
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=None,
        help='Путь к директории с данными'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Файл для записи результата (по умолчанию: stdout)'
    )
    parser.add_argument(
        '--only-unknown',
        action='store_true',
        help='Выводить только эпизоды с неизвестными спикерами'
    )

    args = parser.parse_args()

    # Пути
    script_path = Path(__file__).resolve()
    project_dir = script_path.parent.parent
    data_dir = args.data_dir or (project_dir / 'data_clean')

    # Список эпизодов
    if args.all:
        episodes = sorted([
            int(d.name) for d in data_dir.iterdir()
            if d.is_dir() and d.name.isdigit()
        ])
    elif args.episodes:
        episodes = parse_episodes(args.episodes, data_dir)
    else:
        parser.print_help()
        sys.exit(1)

    print(f"Обработка {len(episodes)} эпизодов...", file=sys.stderr)

    results = []
    for episode in episodes:
        result = process_episode(episode, data_dir)
        if result:
            if args.only_unknown and not result['has_unknown']:
                continue
            results.append(result)

    print(f"Обработано: {len(results)}", file=sys.stderr)
    if args.only_unknown:
        print(f"С неизвестными спикерами: {len(results)}", file=sys.stderr)

    # Вывод
    output = json.dumps(results, ensure_ascii=False, indent=2)

    if args.output:
        args.output.write_text(output, encoding='utf-8')
        print(f"Записано в {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
