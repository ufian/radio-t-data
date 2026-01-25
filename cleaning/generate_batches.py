#!/usr/bin/env python3
"""
Генератор батчей для комьюнити-ревью

Создаёт YAML-файлы с записями для ручной проверки, сгруппированные по:
- Автору и времени речи (короткие реплики - вероятные ошибки)
- Похожим именам для разрешения

Использование:
    python generate_batches.py                    # Сгенерировать все батчи
    python generate_batches.py --author EldarMurtazin  # Только для конкретного автора
    python generate_batches.py --threshold 60     # Порог времени в секундах
"""

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SpeakerEntry:
    """Запись о спикере в эпизоде"""
    episode: int
    author: str
    lines: int
    duration_sec: float
    first_timestamp: str
    first_text: str
    audio_url: str
    context_before: list[str]


def format_timestamp(seconds: float) -> str:
    """Форматирует секунды в MM:SS"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def load_episode_data(data_path: Path, episode: int) -> tuple[dict | None, dict | None]:
    """Загружает CC и DESC данные эпизода"""
    cc_path = data_path / str(episode) / f'{episode}_cc.json'
    desc_path = data_path / str(episode) / f'{episode}_desc.json'

    cc_data = None
    desc_data = None

    if cc_path.exists():
        with open(cc_path, 'r', encoding='utf-8') as f:
            cc_data = json.load(f)

    if desc_path.exists():
        with open(desc_path, 'r', encoding='utf-8') as f:
            desc_data = json.load(f)

    return cc_data, desc_data


def analyze_speaker_in_episode(subs: list[dict], author: str, audio_url: str) -> SpeakerEntry | None:
    """Анализирует спикера в эпизоде"""
    author_subs = []
    for i, sub in enumerate(subs):
        if sub.get('author') == author:
            author_subs.append((i, sub))

    if not author_subs:
        return None

    # Считаем статистику
    total_duration = sum(
        sub.get('etime', 0) - sub.get('stime', 0)
        for _, sub in author_subs
    )

    first_idx, first_sub = author_subs[0]

    # Собираем контекст (2 реплики до)
    context_before = []
    for i in range(max(0, first_idx - 2), first_idx):
        prev_sub = subs[i]
        context_before.append(f"{prev_sub.get('author', 'Unknown')}: {prev_sub.get('text', '')[:80]}")

    # Формируем URL с таймкодом
    start_time = int(first_sub.get('stime', 0))
    audio_with_time = f"{audio_url}#t={start_time}" if audio_url else ""

    episode = first_sub.get('issue', 0)

    return SpeakerEntry(
        episode=episode,
        author=author,
        lines=len(author_subs),
        duration_sec=round(total_duration, 1),
        first_timestamp=format_timestamp(first_sub.get('stime', 0)),
        first_text=first_sub.get('text', ''),
        audio_url=audio_with_time,
        context_before=context_before
    )


def get_episodes(data_path: Path) -> list[int]:
    """Получает список всех эпизодов"""
    episodes = []
    for d in data_path.iterdir():
        if d.is_dir() and d.name.isdigit():
            episodes.append(int(d.name))
    return sorted(episodes)


def collect_speaker_data(data_path: Path, target_author: str) -> list[SpeakerEntry]:
    """Собирает данные о спикере по всем эпизодам"""
    entries = []
    episodes = get_episodes(data_path)

    for episode in episodes:
        cc_data, desc_data = load_episode_data(data_path, episode)
        if not cc_data:
            continue

        subs = cc_data.get('subs', [])
        audio_url = desc_data.get('audio', '') if desc_data else ''

        entry = analyze_speaker_in_episode(subs, target_author, audio_url)
        if entry:
            entries.append(entry)

    return entries


def generate_batch_yaml(entries: list[SpeakerEntry], batch_id: str, description: str) -> dict:
    """Генерирует структуру батча"""
    batch = {
        'batch_id': batch_id,
        'description': description,
        'status': 'open',
        'github_issue': None,
        'entries': []
    }

    for entry in entries:
        batch_entry = {
            'episode': entry.episode,
            'author': entry.author,
            'lines': entry.lines,
            'duration_sec': entry.duration_sec,
            'timestamp': entry.first_timestamp,
            'audio_url': entry.audio_url,
            'text': entry.first_text,
            'context_before': entry.context_before,
            'decision': None
        }
        batch['entries'].append(batch_entry)

    return batch


def save_batch(batch: dict, output_path: Path):
    """Сохраняет батч в YAML файл"""
    # Используем representer для красивого вывода multiline строк
    def str_representer(dumper, data):
        if '\n' in data or len(data) > 80:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    yaml.add_representer(str, str_representer)

    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(batch, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)


def generate_batches_for_author(data_path: Path, output_path: Path, author: str, thresholds: list[tuple[float, float]]):
    """Генерирует батчи для автора по порогам времени"""
    entries = collect_speaker_data(data_path, author)
    print(f"Найдено {len(entries)} эпизодов с {author}")

    # Группируем по порогам
    for i, (min_sec, max_sec) in enumerate(thresholds):
        filtered = [e for e in entries if min_sec <= e.duration_sec < max_sec]
        if not filtered:
            continue

        # Сортируем по времени речи (сначала самые короткие)
        filtered.sort(key=lambda x: x.duration_sec)

        batch_num = str(i + 1).zfill(3)
        batch_id = f"{author.lower()}_{batch_num}"
        description = f"{author} с {min_sec}-{max_sec} сек речи — требует проверки"

        batch = generate_batch_yaml(filtered, batch_id, description)

        filename = f"batch_{batch_id}.yaml"
        save_batch(batch, output_path / filename)

        print(f"  Создан {filename}: {len(filtered)} записей")


def main():
    parser = argparse.ArgumentParser(
        description='Генератор батчей для комьюнити-ревью',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--author', help='Автор для генерации (по умолчанию: все известные гости)')
    parser.add_argument('--threshold', type=float, default=60, help='Максимальный порог времени в секундах')

    args = parser.parse_args()

    # Определяем пути
    script_path = Path(__file__).resolve()
    base_path = script_path.parent.parent
    data_path = base_path / 'data'
    output_path = base_path / 'cleaning' / 'batches'

    output_path.mkdir(parents=True, exist_ok=True)

    # Пороги времени для разбиения на батчи
    thresholds = [
        (0, 10),      # < 10 сек - почти наверняка ошибки
        (10, 30),     # 10-30 сек - вероятные ошибки
        (30, 60),     # 30-60 сек - нужна проверка
    ]

    if args.threshold != 60:
        thresholds = [(0, args.threshold)]

    # Список авторов для обработки
    authors_to_process = ['EldarMurtazin', 'PetrDidenko']

    if args.author:
        authors_to_process = [args.author]

    for author in authors_to_process:
        print(f"\nОбработка {author}:")
        generate_batches_for_author(data_path, output_path, author, thresholds)

    print("\nГенерация батчей завершена!")


if __name__ == '__main__':
    main()
