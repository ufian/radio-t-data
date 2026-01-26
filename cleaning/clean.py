#!/usr/bin/env python3
"""
Система очистки данных подкаста Радио-Т

Применяет правила из конфигов и батчей для очистки разметки спикеров в транскриптах.

Использование:
    python clean.py                          # Применить все конфиги
    python clean.py --config configs/01_normalize.yaml  # Применить конкретный конфиг
    python clean.py --batch batches/batch_eldar_001.yaml  # Применить батч
    python clean.py --dry-run                # Только отчёт, без изменений
    python clean.py --episodes 300-350       # Только указанные эпизоды
"""

import argparse
import json
import os
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ChangeRecord:
    """Запись об изменении"""
    episode: int
    sub_id: str
    old_author: str
    new_author: str
    rule_id: str
    text: str


@dataclass
class CleaningStats:
    """Статистика очистки"""
    episodes_processed: int = 0
    episodes_changed: int = 0
    subs_changed: int = 0
    changes_by_rule: dict = field(default_factory=lambda: defaultdict(int))
    changes: list = field(default_factory=list)


class PeopleRegistry:
    """Реестр участников из people.yaml"""

    def __init__(self, people_path: Path):
        self.people_path = people_path
        self.people = {}
        self.aliases = {}  # alias -> canonical_name
        self._load()

    def _load(self):
        if not self.people_path.exists():
            print(f"Warning: people.yaml not found at {self.people_path}")
            return

        with open(self.people_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Загружаем ведущих
        for host in data.get('hosts', []):
            person_id = host['id']
            canonical = host['canonical_name']
            self.people[person_id] = host
            # Регистрируем aliases
            for alias in host.get('aliases', []):
                self.aliases[alias] = canonical

        # Загружаем гостей
        for guest in data.get('guests', []):
            person_id = guest['id']
            canonical = guest['canonical_name']
            self.people[person_id] = guest
            for alias in guest.get('aliases', []):
                self.aliases[alias] = canonical

        # Загружаем специальных
        for special in data.get('special', []):
            person_id = special['id']
            canonical = special['canonical_name']
            self.people[person_id] = special
            for alias in special.get('aliases', []):
                self.aliases[alias] = canonical

    def get_canonical_name(self, name: str) -> str | None:
        """Возвращает каноническое имя для alias или None"""
        return self.aliases.get(name)

    def get_person_by_id(self, person_id: str) -> dict | None:
        """Возвращает информацию о человеке по ID"""
        return self.people.get(person_id)


class RuleEngine:
    """Движок применения правил"""

    def __init__(self, people: PeopleRegistry):
        self.people = people

    def apply_normalize_aliases(self, subs: list[dict], stats: CleaningStats, episode: int) -> list[dict]:
        """Применяет нормализацию aliases из people.yaml"""
        for sub in subs:
            author = sub.get('author', '')
            canonical = self.people.get_canonical_name(author)
            if canonical and canonical != author:
                stats.changes.append(ChangeRecord(
                    episode=episode,
                    sub_id=sub.get('id', ''),
                    old_author=author,
                    new_author=canonical,
                    rule_id='people_alias',
                    text=sub.get('text', '')[:50]
                ))
                stats.changes_by_rule['people_alias'] += 1
                stats.subs_changed += 1
                sub['author'] = canonical
        return subs

    def apply_duration_threshold(self, subs: list[dict], rule: dict, stats: CleaningStats, episode: int) -> list[dict]:
        """Применяет правило duration_threshold"""
        target_author = rule['author']
        max_duration = rule['max_duration_sec']
        new_author = rule['action']['rename_to']
        rule_id = rule['id']

        # Считаем суммарное время речи автора в эпизоде
        total_duration = 0.0
        author_subs = []
        for sub in subs:
            if sub.get('author') == target_author:
                duration = sub.get('etime', 0) - sub.get('stime', 0)
                total_duration += duration
                author_subs.append(sub)

        # Если суммарное время меньше порога - переименовываем
        if total_duration > 0 and total_duration < max_duration:
            for sub in author_subs:
                stats.changes.append(ChangeRecord(
                    episode=episode,
                    sub_id=sub.get('id', ''),
                    old_author=target_author,
                    new_author=new_author,
                    rule_id=rule_id,
                    text=sub.get('text', '')[:50]
                ))
                stats.changes_by_rule[rule_id] += 1
                stats.subs_changed += 1
                sub['author'] = new_author

        return subs

    def apply_normalize_rule(self, subs: list[dict], rule: dict, stats: CleaningStats, episode: int) -> list[dict]:
        """Применяет правило normalize"""
        from_names = rule['from']
        to_name = rule['to']
        rule_id = rule['id']

        for sub in subs:
            if sub.get('author') in from_names:
                old_author = sub['author']
                stats.changes.append(ChangeRecord(
                    episode=episode,
                    sub_id=sub.get('id', ''),
                    old_author=old_author,
                    new_author=to_name,
                    rule_id=rule_id,
                    text=sub.get('text', '')[:50]
                ))
                stats.changes_by_rule[rule_id] += 1
                stats.subs_changed += 1
                sub['author'] = to_name

        return subs

    def apply_rename_episode_rule(self, subs: list[dict], rule: dict, stats: CleaningStats, episode: int) -> list[dict]:
        """Применяет правило rename_episode (переименование спикера в конкретном эпизоде)"""
        rule_episode = rule.get('episode')
        if rule_episode != episode:
            return subs  # Правило не для этого эпизода

        from_name = rule['from']
        to_name = rule['to']
        rule_id = rule['id']
        time_range = rule.get('time_range')

        for sub in subs:
            if sub.get('author') != from_name:
                continue

            # Проверяем time_range если указан
            if time_range:
                sub_stime = sub.get('stime', 0)
                # Поддерживаем оба формата: список [start, end] и словарь {start, end}
                if isinstance(time_range, list) and len(time_range) >= 2:
                    start, end = time_range[0], time_range[1]
                elif isinstance(time_range, dict):
                    start = time_range.get('start', 0)
                    end = time_range.get('end', float('inf'))
                else:
                    continue  # Неизвестный формат
                if not (start <= sub_stime <= end):
                    continue

            old_author = sub['author']
            stats.changes.append(ChangeRecord(
                episode=episode,
                sub_id=sub.get('id', ''),
                old_author=old_author,
                new_author=to_name,
                rule_id=rule_id,
                text=sub.get('text', '')[:50]
            ))
            stats.changes_by_rule[rule_id] += 1
            stats.subs_changed += 1
            sub['author'] = to_name

        return subs

    def apply_ad_time_range_rule(self, subs: list[dict], rule: dict, stats: CleaningStats, episode: int) -> list[dict]:
        """Применяет правило ad_time_range (любой спикер в диапазоне → _ad)"""
        rule_episode = rule.get('episode')
        if rule_episode != episode:
            return subs

        rule_id = rule['id']
        time_range = rule.get('time_range')
        if not time_range:
            return subs

        # Парсим time_range
        if isinstance(time_range, list) and len(time_range) >= 2:
            start, end = time_range[0], time_range[1]
        elif isinstance(time_range, dict):
            start = time_range.get('start', 0)
            end = time_range.get('end', float('inf'))
        else:
            return subs

        # Исключаем спикеров которых не нужно переименовывать (уже _ad или _artifact)
        exclude_speakers = rule.get('exclude', ['_ad', '_artifact', 'SPEAKER_99'])

        for sub in subs:
            sub_stime = sub.get('stime', 0)
            old_author = sub.get('author', '')

            # Пропускаем если вне диапазона или уже исключён
            if not (start <= sub_stime <= end):
                continue
            if old_author in exclude_speakers:
                continue

            stats.changes.append(ChangeRecord(
                episode=episode,
                sub_id=sub.get('id', ''),
                old_author=old_author,
                new_author='_ad',
                rule_id=rule_id,
                text=sub.get('text', '')[:50]
            ))
            stats.changes_by_rule[rule_id] += 1
            stats.subs_changed += 1
            sub['author'] = '_ad'

        return subs

    def apply_batch_decisions(self, subs: list[dict], entries: list[dict], stats: CleaningStats, episode: int) -> list[dict]:
        """Применяет решения из батча"""
        # Создаём индекс по тексту и времени для быстрого поиска
        subs_by_text = defaultdict(list)
        for sub in subs:
            subs_by_text[sub.get('text', '')].append(sub)

        for entry in entries:
            if entry.get('episode') != episode:
                continue

            decision = entry.get('decision')
            if not decision:
                continue

            person_id = decision.get('person_id')
            if not person_id:
                continue

            # Получаем каноническое имя
            person = self.people.get_person_by_id(person_id)
            if not person:
                print(f"Warning: Unknown person_id '{person_id}' in batch")
                continue

            new_author = person['canonical_name']
            entry_text = entry.get('text', '')
            entry_author = entry.get('author', '')

            # Ищем matching sub
            for sub in subs_by_text.get(entry_text, []):
                if sub.get('author') == entry_author:
                    stats.changes.append(ChangeRecord(
                        episode=episode,
                        sub_id=sub.get('id', ''),
                        old_author=entry_author,
                        new_author=new_author,
                        rule_id=f"batch_{decision.get('verified_by', 'unknown')}",
                        text=entry_text[:50]
                    ))
                    stats.changes_by_rule['batch_decision'] += 1
                    stats.subs_changed += 1
                    sub['author'] = new_author
                    break

        return subs


class CleaningSystem:
    """Основная система очистки"""

    def __init__(self, base_path: Path, dry_run: bool = False):
        self.base_path = base_path
        self.data_path = base_path / 'data'
        self.clean_path = base_path / 'data_clean'
        self.cleaning_path = base_path / 'cleaning'
        self.configs_path = self.cleaning_path / 'configs'
        self.batches_path = self.cleaning_path / 'batches'
        self.dry_run = dry_run

        self.people = PeopleRegistry(self.cleaning_path / 'people.yaml')
        self.engine = RuleEngine(self.people)
        self.stats = CleaningStats()

    def get_episodes(self, episode_range: str | None = None) -> list[int]:
        """Получает список эпизодов для обработки"""
        episodes = []
        for d in self.data_path.iterdir():
            if d.is_dir() and d.name.isdigit():
                episodes.append(int(d.name))

        episodes.sort()

        if episode_range:
            if '-' in episode_range:
                start, end = episode_range.split('-')
                start = int(start) if start else 0
                end = int(end) if end else max(episodes)
                episodes = [e for e in episodes if start <= e <= end]
            else:
                episodes = [int(episode_range)]

        return episodes

    def load_configs(self, config_path: str | None = None) -> list[dict]:
        """Загружает конфиги из папки configs/"""
        configs = []

        if config_path:
            path = Path(config_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    configs.append(yaml.safe_load(f))
            return configs

        # Загружаем все конфиги из configs/
        if self.configs_path.exists():
            for config_file in sorted(self.configs_path.glob('*.yaml')):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    config['_file'] = str(config_file)
                    configs.append(config)

        # Сортируем по приоритету
        configs.sort(key=lambda c: c.get('priority', 100))
        return configs

    def load_batches(self, batch_path: str | None = None) -> list[dict]:
        """Загружает батчи из папки batches/"""
        batches = []

        if batch_path:
            path = Path(batch_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    batches.append(yaml.safe_load(f))
            return batches

        # Загружаем все батчи
        if self.batches_path.exists():
            for batch_file in sorted(self.batches_path.glob('*.yaml')):
                with open(batch_file, 'r', encoding='utf-8') as f:
                    batch = yaml.safe_load(f)
                    # Пропускаем незавершённые батчи
                    if batch.get('status') == 'completed':
                        batch['_file'] = str(batch_file)
                        batches.append(batch)

        return batches

    def load_episode_data(self, episode: int) -> dict | None:
        """Загружает данные эпизода"""
        cc_path = self.data_path / str(episode) / f'{episode}_cc.json'
        if not cc_path.exists():
            return None

        with open(cc_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_episode_data(self, episode: int, data: dict):
        """Сохраняет очищенные данные"""
        if self.dry_run:
            return

        episode_dir = self.clean_path / str(episode)
        episode_dir.mkdir(parents=True, exist_ok=True)

        cc_path = episode_dir / f'{episode}_cc.json'
        with open(cc_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def process_episode(self, episode: int, configs: list[dict], batches: list[dict]) -> bool:
        """Обрабатывает один эпизод"""
        data = self.load_episode_data(episode)
        if not data:
            return False

        subs = data.get('subs', [])
        original_subs = json.dumps(subs)  # Для проверки изменений

        # Применяем конфиги
        for config in configs:
            # Нормализация aliases из people.yaml
            if config.get('use_people_aliases'):
                subs = self.engine.apply_normalize_aliases(subs, self.stats, episode)

            # Применяем правила из конфига
            rules = config.get('rules') or []
            for rule in rules:
                rule_type = rule.get('type')

                if rule_type == 'duration_threshold':
                    subs = self.engine.apply_duration_threshold(subs, rule, self.stats, episode)
                elif rule_type == 'normalize':
                    subs = self.engine.apply_normalize_rule(subs, rule, self.stats, episode)
                elif rule_type == 'rename_episode':
                    subs = self.engine.apply_rename_episode_rule(subs, rule, self.stats, episode)
                elif rule_type == 'ad_time_range':
                    subs = self.engine.apply_ad_time_range_rule(subs, rule, self.stats, episode)

        # Применяем батчи
        for batch in batches:
            entries = batch.get('entries', [])
            subs = self.engine.apply_batch_decisions(subs, entries, self.stats, episode)

        # Проверяем были ли изменения
        changed = json.dumps(subs) != original_subs
        if changed:
            data['subs'] = subs
            self.stats.episodes_changed += 1

        # Сохраняем всегда (даже если изменений нет)
        self.save_episode_data(episode, data)

        self.stats.episodes_processed += 1
        return changed

    def run(self, config_path: str | None = None, batch_path: str | None = None, episode_range: str | None = None):
        """Запускает очистку"""
        episodes = self.get_episodes(episode_range)
        configs = self.load_configs(config_path)
        batches = self.load_batches(batch_path)

        print(f"Загружено конфигов: {len(configs)}")
        print(f"Загружено батчей: {len(batches)}")
        print(f"Эпизодов для обработки: {len(episodes)}")
        if self.dry_run:
            print("Режим: DRY RUN (изменения не сохраняются)")
        print()

        for episode in episodes:
            self.process_episode(episode, configs, batches)

        self.print_report()

    def print_report(self):
        """Печатает отчёт о выполненной работе"""
        print("\n" + "=" * 60)
        print("ОТЧЁТ О ВЫПОЛНЕННОЙ ОЧИСТКЕ")
        print("=" * 60)
        print(f"Эпизодов обработано: {self.stats.episodes_processed}")
        print(f"Эпизодов изменено: {self.stats.episodes_changed}")
        print(f"Записей изменено: {self.stats.subs_changed}")
        print()

        if self.stats.changes_by_rule:
            print("Изменения по правилам:")
            for rule_id, count in sorted(self.stats.changes_by_rule.items()):
                print(f"  {rule_id}: {count}")
            print()

        if self.stats.changes and len(self.stats.changes) <= 50:
            print("Детали изменений:")
            for change in self.stats.changes:
                print(f"  Эпизод {change.episode}: {change.old_author} -> {change.new_author}")
                print(f"    Правило: {change.rule_id}")
                print(f"    Текст: {change.text}...")
                print()


def main():
    parser = argparse.ArgumentParser(
        description='Система очистки данных подкаста Радио-Т',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--config', help='Путь к конкретному конфигу')
    parser.add_argument('--batch', help='Путь к конкретному батчу')
    parser.add_argument('--episodes', help='Диапазон эпизодов (например: 300-350 или 307)')
    parser.add_argument('--dry-run', action='store_true', help='Только отчёт, без изменений')

    args = parser.parse_args()

    # Определяем базовый путь
    script_path = Path(__file__).resolve()
    base_path = script_path.parent.parent

    system = CleaningSystem(base_path, dry_run=args.dry_run)
    system.run(
        config_path=args.config,
        batch_path=args.batch,
        episode_range=args.episodes
    )


if __name__ == '__main__':
    main()
