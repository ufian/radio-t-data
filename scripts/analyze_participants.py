#!/usr/bin/env python3
"""
Анализ участников подкаста Радио-Т
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path


def normalize_author(author):
    """Нормализация имени автора с учётом вариаций"""
    if not author:
        return None

    author = author.strip()

    # Объединение вариаций
    variations = {
        'Grey': 'Gray',
        ' Gray': 'Gray',
        'Alex.sys': 'Alek.sys',
        ' Umputun': 'Umputun',
    }

    return variations.get(author, author)


def is_unknown_guest(author):
    """Проверка на неизвестного гостя"""
    if not author:
        return False

    # Guest, Guest1-Guest29, Guest_01, Guest_02
    if re.match(r'^Guest(_?\d+)?$', author):
        return True

    # SPEAKER_00 - SPEAKER_99
    if re.match(r'^SPEAKER_\d+$', author):
        return True

    return False


def is_special_marker(author):
    """Проверка на специальные маркеры (реклама и т.п.)"""
    if not author:
        return False
    return author in ['_ad', '_extra']


def should_exclude(author):
    """Проверка на исключаемых авторов для списка известных участников"""
    if not author:
        return True

    exclude_list = ['Unknown', 'GPT', 'ElevenLabs', '_ad', '_extra', '']

    if author in exclude_list:
        return True

    # Исключаем неизвестных гостей из основного списка
    if is_unknown_guest(author):
        return True

    return False


def load_episode_cc(episode_num):
    """Загрузка файла субтитров выпуска"""
    cc_path = Path(f'data/{episode_num}/{episode_num}_cc.json')
    if not cc_path.exists():
        return None

    try:
        with open(cc_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('subs', [])
    except (json.JSONDecodeError, IOError):
        return None


def analyze_participants():
    """Основной анализ участников"""

    # Статистика известных участников
    known_participants = defaultdict(lambda: {'lines': 0, 'episodes': set()})

    # Неизвестные гости с контекстом
    unknown_guests = []

    # Комбинации неизвестных по выпускам
    unknown_combinations = defaultdict(list)

    # Проходим по всем выпускам
    for episode_num in range(0, 992):
        subs = load_episode_cc(episode_num)
        if not subs:
            continue

        episode_unknown = set()
        episode_markers = set()  # _ad, _extra
        episode_known = set()

        # Первый проход: собираем статистику
        for sub in subs:
            author = normalize_author(sub.get('author', ''))

            if not author:
                continue

            if is_unknown_guest(author):
                episode_unknown.add(author)
            elif is_special_marker(author):
                episode_markers.add(author)
            elif not should_exclude(author):
                known_participants[author]['lines'] += 1
                known_participants[author]['episodes'].add(episode_num)
                episode_known.add(author)

        # Комбинация неизвестных + маркеров
        all_unknown = episode_unknown | episode_markers

        # Если есть неизвестные гости или маркеры, собираем контекст
        if all_unknown:
            # Сохраняем комбинацию (включая маркеры)
            combo_key = tuple(sorted(all_unknown))
            unknown_combinations[combo_key].append(episode_num)

            # Для каждого неизвестного гостя находим контекст
            for unknown_author in episode_unknown:
                # Пропускаем SPEAKER_* с короткими репликами
                if unknown_author.startswith('SPEAKER_'):
                    # Проверяем длину реплик
                    guest_lines = [s for s in subs if normalize_author(s.get('author')) == unknown_author]
                    max_len = max(len(s.get('text', '')) for s in guest_lines) if guest_lines else 0
                    if max_len <= 10:
                        continue

                # Находим первую реплику гостя
                first_guest_idx = None
                for idx, sub in enumerate(subs):
                    if normalize_author(sub.get('author')) == unknown_author:
                        first_guest_idx = idx
                        break

                if first_guest_idx is None:
                    continue

                # Берём 20 реплик до первого появления
                context_start = max(0, first_guest_idx - 20)
                context_lines = []
                for i in range(context_start, first_guest_idx):
                    sub = subs[i]
                    author = normalize_author(sub.get('author', ''))
                    text = sub.get('text', '')
                    if author and text and not should_exclude(author):
                        context_lines.append(f"{author}: {text}")

                # Первые 3 реплики гостя
                guest_lines = []
                guest_count = 0
                for i in range(first_guest_idx, len(subs)):
                    sub = subs[i]
                    if normalize_author(sub.get('author')) == unknown_author:
                        guest_lines.append(sub.get('text', ''))
                        guest_count += 1
                        if guest_count >= 3:
                            break

                unknown_guests.append({
                    'episode': episode_num,
                    'guest': unknown_author,
                    'context': context_lines[-10:],  # Последние 10 реплик контекста
                    'first_lines': guest_lines
                })

    return known_participants, unknown_guests, unknown_combinations


def create_participants_md(participants):
    """Создание файла participants.md"""
    lines = ['# Участники подкаста Радио-Т\n\n']
    lines.append('| Имя | Реплик | Выпуски |\n')
    lines.append('|-----|--------|--------|\n')

    # Сортируем по количеству реплик
    sorted_participants = sorted(
        participants.items(),
        key=lambda x: x[1]['lines'],
        reverse=True
    )

    for name, stats in sorted_participants:
        episodes = sorted(stats['episodes'])
        if len(episodes) > 10:
            episodes_str = f"{episodes[0]}-{episodes[-1]} ({len(episodes)} вып.)"
        else:
            episodes_str = ', '.join(map(str, episodes))

        lines.append(f"| {name} | {stats['lines']} | {episodes_str} |\n")

    with open('participants.md', 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"Создан participants.md с {len(participants)} участниками")


def create_unknown_guests_md(unknown_guests):
    """Создание файла unknown_guests.md"""
    lines = ['# Неизвестные гости подкаста Радио-Т\n\n']
    lines.append('Для каждого неизвестного гостя приведён контекст для идентификации.\n\n')

    # Группируем по выпускам
    by_episode = defaultdict(list)
    for guest in unknown_guests:
        by_episode[guest['episode']].append(guest)

    for episode_num in sorted(by_episode.keys()):
        lines.append(f'## Выпуск {episode_num}\n\n')

        for guest_info in by_episode[episode_num]:
            lines.append(f"### {guest_info['guest']}\n\n")

            if guest_info['context']:
                lines.append("**Контекст (до появления):**\n```\n")
                for ctx in guest_info['context']:
                    lines.append(f"{ctx}\n")
                lines.append("```\n\n")

            if guest_info['first_lines']:
                lines.append("**Первые реплики:**\n```\n")
                for line in guest_info['first_lines']:
                    lines.append(f"{line}\n")
                lines.append("```\n\n")

    with open('unknown_guests.md', 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"Создан unknown_guests.md с {len(unknown_guests)} записями в {len(by_episode)} выпусках")


def create_unknown_combinations_md(combinations):
    """Создание файла unknown_combinations.md"""
    lines = ['# Комбинации неизвестных гостей\n\n']
    lines.append('Агрегированная статистика по комбинациям неизвестных участников.\n\n')

    lines.append('| Комбинация | Выпусков | Примеры выпусков |\n')
    lines.append('|------------|----------|------------------|\n')

    # Сортируем по количеству выпусков
    sorted_combos = sorted(
        combinations.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    for combo, episodes in sorted_combos:
        combo_str = ', '.join(combo) if combo else '(пусто)'
        examples = ', '.join(map(str, episodes[:5]))
        if len(episodes) > 5:
            examples += '...'
        lines.append(f"| {combo_str} | {len(episodes)} | {examples} |\n")

    lines.append('\n## Анализ\n\n')

    # Считаем категории
    ad_only = 0
    ad_with_speaker = 0
    speaker_only = 0
    guest_only = 0
    guest_with_ad = 0
    mixed = 0

    for combo, episodes in combinations.items():
        has_ad = '_ad' in combo
        has_extra = '_extra' in combo
        has_speaker = any(c.startswith('SPEAKER_') for c in combo)
        has_guest = any(c.startswith('Guest') for c in combo)

        # Классификация
        if combo == ('_ad',):
            ad_only += len(episodes)
        elif has_ad and has_speaker and not has_guest:
            ad_with_speaker += len(episodes)
        elif has_speaker and not has_ad and not has_guest:
            speaker_only += len(episodes)
        elif has_guest and not has_speaker:
            if has_ad:
                guest_with_ad += len(episodes)
            else:
                guest_only += len(episodes)
        else:
            mixed += len(episodes)

    total = ad_only + ad_with_speaker + speaker_only + guest_only + guest_with_ad + mixed

    lines.append(f'- **Только реклама (_ad):** {ad_only} выпусков\n')
    lines.append(f'- **_ad + SPEAKER_*:** {ad_with_speaker} выпусков\n')
    lines.append(f'- **Только SPEAKER_* (без _ad):** {speaker_only} выпусков\n')
    lines.append(f'- **Guest* (без SPEAKER_*):** {guest_only} выпусков\n')
    lines.append(f'- **Guest* + _ad:** {guest_with_ad} выпусков\n')
    lines.append(f'- **Смешанные (Guest + SPEAKER):** {mixed} выпусков\n')
    lines.append(f'\n**Всего:** {total} выпусков с неизвестными/маркерами\n')

    with open('unknown_combinations.md', 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"Создан unknown_combinations.md с {len(combinations)} уникальными комбинациями")


def main():
    print("Анализ участников подкаста Радио-Т...")

    participants, unknown_guests, combinations = analyze_participants()

    create_participants_md(participants)
    create_unknown_guests_md(unknown_guests)
    create_unknown_combinations_md(combinations)

    print("\nГотово!")


if __name__ == '__main__':
    main()
