#!/usr/bin/env python3
"""
Извлечение правил из validation файлов и категоризация.

Создаёт:
- cleaning/configs/03_from_validation.yaml - автоматические правила (high confidence)
- cleaning/configs/04_artifacts.yaml - правила для артефактов (is_error: true, < 5 сек)
- cleaning/tasks/voice_matching/ - задачи на voice comparison
- cleaning/tasks/manual_review/ - задачи на ручной ревью
"""

import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ExtractedRule:
    """Извлечённое правило"""
    episode: int
    rule_type: str
    from_speaker: str
    to_speaker: str | None
    confidence: str | float
    reason: str
    time_range: dict | None = None
    stime: float | None = None
    etime: float | None = None

    def to_dict(self) -> dict:
        d = {
            'episode': self.episode,
            'from_speaker': self.from_speaker,
            'to_speaker': self.to_speaker,
            'confidence': self.confidence,
            'reason': self.reason.strip() if self.reason else '',
        }
        if self.time_range:
            d['time_range'] = self.time_range
        if self.stime is not None:
            d['stime'] = self.stime
        if self.etime is not None:
            d['etime'] = self.etime
        return d


@dataclass
class VoiceTask:
    """Задача на voice comparison"""
    episode: int
    speaker: str
    total_duration_sec: float
    replies_count: int
    reference_segment: dict | None
    reason: str
    possible_matches: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'episode': self.episode,
            'speaker': self.speaker,
            'total_duration_sec': self.total_duration_sec,
            'replies_count': self.replies_count,
            'reference_segment': self.reference_segment,
            'reason': self.reason,
            'possible_matches': self.possible_matches,
        }


@dataclass
class ArtifactRule:
    """Правило для артефакта"""
    episode: int
    speaker: str
    total_duration_sec: float
    replies_count: int
    reason: str

    def to_dict(self) -> dict:
        return {
            'episode': self.episode,
            'from_speaker': self.speaker,
            'to_speaker': '_artifact',
            'total_duration_sec': self.total_duration_sec,
            'replies_count': self.replies_count,
            'reason': self.reason,
        }


class RuleExtractor:
    """Извлекает правила из validation файлов"""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.validation_path = base_path / 'validation' / 'episodes'
        self.cleaning_path = base_path / 'cleaning'

        # Категории правил
        self.auto_rules: list[ExtractedRule] = []  # high confidence
        self.artifact_rules: list[ArtifactRule] = []  # is_error: true, short
        self.ad_rules: list[ExtractedRule] = []  # host in ad → _ad
        self.voice_tasks: list[VoiceTask] = []  # voice comparison needed
        self.manual_review: list[dict] = []  # needs manual review
        self.new_guests: list[dict] = []  # new_guest_for_registry

        # Загружаем people.yaml для маппинга id → canonical_name
        self.people_map = {}  # id -> canonical_name
        self._load_people()

        # Статистика
        self.stats = defaultdict(int)

    def _load_people(self):
        """Загружает people.yaml и создаёт маппинг id → canonical_name"""
        people_path = self.cleaning_path / 'people.yaml'
        if not people_path.exists():
            print(f"Warning: people.yaml not found at {people_path}")
            return

        with open(people_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        for category in ['hosts', 'guests', 'special']:
            for person in data.get(category, []):
                person_id = person.get('id')
                canonical = person.get('canonical_name')
                if person_id and canonical:
                    self.people_map[person_id] = canonical

        print(f"Загружено {len(self.people_map)} записей из people.yaml")

    def get_canonical_name(self, name: str) -> str:
        """Возвращает canonical_name для person_id, или сам name если не найден"""
        return self.people_map.get(name, name)

    def parse_confidence(self, conf) -> tuple[str, float]:
        """Парсит confidence в категорию и числовое значение"""
        if conf is None:
            return ('unknown', 0.0)
        if isinstance(conf, str):
            if conf == 'high':
                return ('high', 0.9)
            elif conf == 'medium':
                return ('medium', 0.5)
            elif conf == 'low':
                return ('low', 0.2)
            else:
                return ('unknown', 0.0)
        elif isinstance(conf, (int, float)):
            if conf >= 0.8:
                return ('high', float(conf))
            elif conf >= 0.5:
                return ('medium', float(conf))
            else:
                return ('low', float(conf))
        return ('unknown', 0.0)

    def process_unknown_speaker(self, episode: int, speaker_data: dict):
        """Обрабатывает unknown_speaker из validation файла"""
        speaker = speaker_data.get('speaker', '')
        total_duration = speaker_data.get('total_duration_sec', 0)
        replies_count = speaker_data.get('replies_count', 0)
        analysis = speaker_data.get('analysis', {})

        is_error = analysis.get('is_error', False)
        identified_as = analysis.get('identified_as')
        conf_str = analysis.get('confidence')
        conf_category, conf_value = self.parse_confidence(conf_str)
        evidence = analysis.get('evidence', '')
        error_reason = analysis.get('error_reason', '')
        voice_task = analysis.get('voice_task', {})
        voice_needed = voice_task.get('needed', False) if voice_task else False
        reference_segment = voice_task.get('reference_segment') if voice_task else None
        possible_matches = analysis.get('possible_matches', [])

        # 1. Артефакты (is_error: true, < 5 сек)
        if is_error and total_duration is not None and total_duration < 5:
            self.artifact_rules.append(ArtifactRule(
                episode=episode,
                speaker=speaker,
                total_duration_sec=total_duration,
                replies_count=replies_count,
                reason=str(error_reason)[:200] if error_reason else 'is_error: true, short duration'
            ))
            self.stats['artifacts'] += 1
            return

        # 2. SPEAKER_MISATTRIBUTED_* с коротким временем (< 10 сек) → _artifact
        if speaker.startswith('SPEAKER_MISATTRIBUTED_') and total_duration is not None and total_duration < 10:
            self.artifact_rules.append(ArtifactRule(
                episode=episode,
                speaker=speaker,
                total_duration_sec=total_duration,
                replies_count=replies_count,
                reason=f'MISATTRIBUTED with short duration ({total_duration:.1f}s)'
            ))
            self.stats['misattributed_short'] += 1
            return

        # 3. Идентифицированные с high confidence → auto_rules
        if identified_as and conf_category == 'high':
            canonical_name = self.get_canonical_name(identified_as)
            self.auto_rules.append(ExtractedRule(
                episode=episode,
                rule_type='rename',
                from_speaker=speaker,
                to_speaker=canonical_name,
                confidence=conf_str,
                reason=str(evidence)[:300] if evidence else 'high confidence identification'
            ))
            self.stats['auto_high'] += 1
            return

        # 4. Voice task needed или medium/low confidence с достаточным временем → voice_tasks
        if (voice_needed or conf_category in ('medium', 'low', 'unknown')) and total_duration is not None and total_duration >= 10:
            self.voice_tasks.append(VoiceTask(
                episode=episode,
                speaker=speaker,
                total_duration_sec=total_duration,
                replies_count=replies_count,
                reference_segment=reference_segment,
                reason=str(evidence or error_reason)[:300] if (evidence or error_reason) else 'needs voice comparison',
                possible_matches=possible_matches
            ))
            self.stats['voice_tasks'] += 1
            return

        # 5. Идентифицированные с medium confidence → manual_review (но можно применить)
        if identified_as and conf_category == 'medium':
            canonical_name = self.get_canonical_name(identified_as)
            self.manual_review.append({
                'episode': episode,
                'speaker': speaker,
                'identified_as': canonical_name,
                'confidence': conf_str,
                'total_duration_sec': total_duration,
                'evidence': str(evidence)[:300] if evidence else '',
                'action': 'confirm_or_reject'
            })
            self.stats['manual_medium'] += 1
            return

        # 6. Остальное → manual_review
        if total_duration is not None and total_duration >= 5:
            self.manual_review.append({
                'episode': episode,
                'speaker': speaker,
                'total_duration_sec': total_duration,
                'replies_count': replies_count,
                'is_error': is_error,
                'identified_as': identified_as,
                'confidence': conf_str,
                'action': 'investigate'
            })
            self.stats['manual_other'] += 1

    def process_suggested_rule(self, episode: int, rule: dict):
        """Обрабатывает suggested_rule из validation файла"""
        rule_type = rule.get('type', 'rename')
        from_speaker = rule.get('from_speaker', '')
        to_speaker = rule.get('to_speaker')
        conf_str = rule.get('confidence')
        conf_category, conf_value = self.parse_confidence(conf_str)
        reason = rule.get('reason', '')
        time_range = rule.get('time_range')

        # Пропускаем пустые правила
        if not from_speaker:
            return

        # Правила для рекламы (host → _ad)
        if to_speaker == '_ad':
            self.ad_rules.append(ExtractedRule(
                episode=episode,
                rule_type=rule_type,
                from_speaker=from_speaker,
                to_speaker='_ad',
                confidence=conf_str,
                reason=str(reason)[:200] if reason else 'host in advertisement',
                time_range=time_range
            ))
            self.stats['ad_rules'] += 1
            return

        # High confidence → auto_rules
        if conf_category == 'high' and to_speaker:
            canonical_name = self.get_canonical_name(to_speaker)
            self.auto_rules.append(ExtractedRule(
                episode=episode,
                rule_type=rule_type,
                from_speaker=from_speaker,
                to_speaker=canonical_name,
                confidence=conf_str,
                reason=str(reason)[:200] if reason else 'high confidence from suggested_rules',
                time_range=time_range
            ))
            self.stats['auto_suggested'] += 1
            return

        # Medium/low → manual_review
        if to_speaker:
            canonical_name = self.get_canonical_name(to_speaker)
            self.manual_review.append({
                'episode': episode,
                'from_speaker': from_speaker,
                'to_speaker': canonical_name,
                'confidence': conf_str,
                'reason': str(reason)[:200] if reason else '',
                'time_range': time_range,
                'action': 'confirm_or_reject'
            })
            self.stats['manual_suggested'] += 1

    def process_validation_file(self, filepath: Path):
        """Обрабатывает один validation файл"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return

        if not data:
            return

        episode = data.get('episode')
        if episode is None:
            return

        self.stats['files_processed'] += 1

        # Обрабатываем unknown_speakers
        for speaker_data in data.get('unknown_speakers', []):
            self.process_unknown_speaker(episode, speaker_data)

        # Обрабатываем suggested_rules
        for rule in data.get('suggested_rules', []):
            self.process_suggested_rule(episode, rule)

        # Собираем new_guest_for_registry
        new_guest = data.get('new_guest_for_registry')
        if new_guest:
            new_guest['episode'] = episode
            self.new_guests.append(new_guest)
            self.stats['new_guests'] += 1

    def run(self):
        """Запускает извлечение из всех validation файлов"""
        print("Сканирование validation файлов...")

        for batch_dir in sorted(self.validation_path.iterdir()):
            if not batch_dir.is_dir():
                continue

            for yaml_file in sorted(batch_dir.glob('*.yaml')):
                self.process_validation_file(yaml_file)

        print(f"\nОбработано файлов: {self.stats['files_processed']}")
        print(f"Артефакты (_artifact): {self.stats['artifacts']}")
        print(f"MISATTRIBUTED короткие: {self.stats['misattributed_short']}")
        print(f"Auto high confidence: {self.stats['auto_high']}")
        print(f"Auto suggested rules: {self.stats['auto_suggested']}")
        print(f"AD rules: {self.stats['ad_rules']}")
        print(f"Voice tasks: {self.stats['voice_tasks']}")
        print(f"Manual review (medium): {self.stats['manual_medium']}")
        print(f"Manual review (other): {self.stats['manual_other']}")
        print(f"Manual suggested: {self.stats['manual_suggested']}")
        print(f"New guests: {self.stats['new_guests']}")

    def deduplicate_rules(self, rules: list[ExtractedRule]) -> list[ExtractedRule]:
        """Дедуплицирует правила по ключу (episode, from_speaker, to_speaker)"""
        seen = set()
        unique_rules = []
        for rule in rules:
            key = (rule.episode, rule.from_speaker, rule.to_speaker)
            if key not in seen:
                seen.add(key)
                unique_rules.append(rule)
        return unique_rules

    def save_configs(self):
        """Сохраняет конфиги и задачи"""
        # Создаём директории
        configs_path = self.cleaning_path / 'configs'
        tasks_path = self.cleaning_path / 'tasks'
        voice_path = tasks_path / 'voice_matching'
        review_path = tasks_path / 'manual_review'

        configs_path.mkdir(parents=True, exist_ok=True)
        voice_path.mkdir(parents=True, exist_ok=True)
        review_path.mkdir(parents=True, exist_ok=True)

        # Дедуплицируем правила
        self.auto_rules = self.deduplicate_rules(self.auto_rules)
        self.ad_rules = self.deduplicate_rules(self.ad_rules)

        # 1. Auto rules (high confidence)
        if self.auto_rules:
            auto_config = {
                'version': 1,
                'name': 'Auto-extracted rules from validation (high confidence)',
                'priority': 3,
                'description': 'Правила извлечённые из validation файлов с high confidence',
                'rules': []
            }

            # Группируем по эпизодам
            by_episode = defaultdict(list)
            for rule in self.auto_rules:
                by_episode[rule.episode].append(rule)

            for episode in sorted(by_episode.keys()):
                for rule in by_episode[episode]:
                    auto_config['rules'].append({
                        'id': f'auto_e{episode}_{rule.from_speaker}_{rule.to_speaker}',
                        'type': 'rename_episode',
                        'episode': episode,
                        'from': rule.from_speaker,
                        'to': rule.to_speaker,
                        'reason': rule.reason
                    })

            with open(configs_path / '03_from_validation.yaml', 'w', encoding='utf-8') as f:
                yaml.dump(auto_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            print(f"\nСохранено: {configs_path / '03_from_validation.yaml'} ({len(self.auto_rules)} правил)")

        # 2. Artifact rules
        if self.artifact_rules:
            artifact_config = {
                'version': 1,
                'name': 'Artifact rules (short transcription errors)',
                'priority': 4,
                'description': 'Короткие ошибки транскрипции → _artifact',
                'rules': []
            }

            by_episode = defaultdict(list)
            for rule in self.artifact_rules:
                by_episode[rule.episode].append(rule)

            for episode in sorted(by_episode.keys()):
                for rule in by_episode[episode]:
                    artifact_config['rules'].append({
                        'id': f'artifact_e{episode}_{rule.speaker}',
                        'type': 'rename_episode',
                        'episode': episode,
                        'from': rule.speaker,
                        'to': '_artifact',
                        'reason': rule.reason
                    })

            with open(configs_path / '04_artifacts.yaml', 'w', encoding='utf-8') as f:
                yaml.dump(artifact_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            print(f"Сохранено: {configs_path / '04_artifacts.yaml'} ({len(self.artifact_rules)} правил)")

        # 3. AD rules
        if self.ad_rules:
            ad_config = {
                'version': 1,
                'name': 'Advertisement rules (hosts in ads → _ad)',
                'priority': 5,
                'description': 'Ведущие в рекламных блоках → _ad',
                'rules': []
            }

            for rule in self.ad_rules:
                rule_dict = {
                    'id': f'ad_e{rule.episode}_{rule.from_speaker}',
                    'type': 'rename_episode',
                    'episode': rule.episode,
                    'from': rule.from_speaker,
                    'to': '_ad',
                    'reason': rule.reason
                }
                if rule.time_range:
                    rule_dict['time_range'] = rule.time_range
                ad_config['rules'].append(rule_dict)

            with open(configs_path / '05_advertisements.yaml', 'w', encoding='utf-8') as f:
                yaml.dump(ad_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            print(f"Сохранено: {configs_path / '05_advertisements.yaml'} ({len(self.ad_rules)} правил)")

        # 4. Voice tasks - группируем по батчам (100 эпизодов)
        if self.voice_tasks:
            by_batch = defaultdict(list)
            for task in self.voice_tasks:
                batch = (task.episode // 100) * 100
                by_batch[batch].append(task)

            for batch, tasks in sorted(by_batch.items()):
                batch_data = {
                    'batch_id': f'voice_{batch:04d}_{batch+99:04d}',
                    'description': f'Voice matching tasks for episodes {batch}-{batch+99}',
                    'status': 'pending',
                    'total_tasks': len(tasks),
                    'tasks': [t.to_dict() for t in sorted(tasks, key=lambda x: x.episode)]
                }

                filename = f'batch_{batch:04d}_{batch+99:04d}.yaml'
                with open(voice_path / filename, 'w', encoding='utf-8') as f:
                    yaml.dump(batch_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            print(f"Сохранено: {voice_path}/ ({len(self.voice_tasks)} задач в {len(by_batch)} батчах)")

        # 5. Manual review - группируем по батчам
        if self.manual_review:
            by_batch = defaultdict(list)
            for item in self.manual_review:
                episode = item.get('episode', 0)
                batch = (episode // 100) * 100
                by_batch[batch].append(item)

            for batch, items in sorted(by_batch.items()):
                batch_data = {
                    'batch_id': f'review_{batch:04d}_{batch+99:04d}',
                    'description': f'Manual review tasks for episodes {batch}-{batch+99}',
                    'status': 'pending',
                    'total_tasks': len(items),
                    'tasks': sorted(items, key=lambda x: x.get('episode', 0))
                }

                filename = f'batch_{batch:04d}_{batch+99:04d}.yaml'
                with open(review_path / filename, 'w', encoding='utf-8') as f:
                    yaml.dump(batch_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            print(f"Сохранено: {review_path}/ ({len(self.manual_review)} задач в {len(by_batch)} батчах)")

        # 6. New guests for people.yaml
        if self.new_guests:
            guests_data = {
                'description': 'New guests to add to people.yaml',
                'total': len(self.new_guests),
                'guests': self.new_guests
            }

            with open(tasks_path / 'new_guests.yaml', 'w', encoding='utf-8') as f:
                yaml.dump(guests_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            print(f"Сохранено: {tasks_path / 'new_guests.yaml'} ({len(self.new_guests)} гостей)")

    def print_summary(self):
        """Печатает сводку"""
        print("\n" + "=" * 60)
        print("СВОДКА ИЗВЛЕЧЁННЫХ ПРАВИЛ")
        print("=" * 60)

        total_auto = len(self.auto_rules) + len(self.artifact_rules) + len(self.ad_rules)
        total_manual = len(self.voice_tasks) + len(self.manual_review)

        print(f"\nАВТОМАТИЧЕСКИЕ ПРАВИЛА (можно применить сразу): {total_auto}")
        print(f"  - High confidence renames: {len(self.auto_rules)}")
        print(f"  - Artifacts (_artifact): {len(self.artifact_rules)}")
        print(f"  - Advertisement (_ad): {len(self.ad_rules)}")

        print(f"\nТРЕБУЮТ ОБРАБОТКИ: {total_manual}")
        print(f"  - Voice matching: {len(self.voice_tasks)}")
        print(f"  - Manual review: {len(self.manual_review)}")

        print(f"\nДОПОЛНИТЕЛЬНО:")
        print(f"  - New guests for people.yaml: {len(self.new_guests)}")
        print("=" * 60)


def main():
    # Определяем базовый путь
    script_path = Path(__file__).resolve()
    base_path = script_path.parent.parent

    extractor = RuleExtractor(base_path)
    extractor.run()
    extractor.save_configs()
    extractor.print_summary()


if __name__ == '__main__':
    main()
