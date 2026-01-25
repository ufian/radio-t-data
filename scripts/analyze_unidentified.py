#!/usr/bin/env python3
"""
Анализ нераспознанных гостей
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter


def load_json_safe(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def main():
    # Загружаем всех гостей для анализа
    all_guests = load_json_safe('guests_to_analyze.json')
    print(f"Всего гостей для анализа: {len(all_guests)}")

    # Загружаем идентифицированных
    identified = load_json_safe('all_identified_guests.json')
    identified_keys = {(r['episode'], r['guest_id']) for r in identified}
    print(f"Идентифицировано: {len(identified_keys)}")

    # Находим нераспознанных
    unidentified = []
    for g in all_guests:
        key = (g['episode'], g['guest_id'])
        if key not in identified_keys:
            unidentified.append(g)

    print(f"Нераспознано: {len(unidentified)}")

    # === СТАТИСТИКА ПО ТИПАМ ===
    print("\n=== СТАТИСТИКА ПО ТИПАМ ГОСТЕЙ ===")

    type_counts = Counter()
    for g in unidentified:
        guest_id = g['guest_id']
        if guest_id.startswith('SPEAKER_'):
            num = int(guest_id.replace('SPEAKER_', ''))
            if num == 99:
                type_counts['SPEAKER_99 (джинглы/эффекты)'] += 1
            else:
                type_counts[f'SPEAKER_0{num}' if num < 10 else f'SPEAKER_{num}'] += 1
        elif re.match(r'^Guest\d+$', guest_id):
            type_counts['Guest1-Guest29'] += 1
        elif guest_id == 'Guest':
            type_counts['Guest (без номера)'] += 1
        elif re.match(r'^Guest_\d+$', guest_id):
            type_counts['Guest_01, Guest_02'] += 1
        else:
            type_counts[guest_id] += 1

    # Группируем SPEAKER_*
    speaker_total = sum(v for k, v in type_counts.items() if 'SPEAKER_' in k)
    guest_total = sum(v for k, v in type_counts.items() if 'Guest' in k)

    print(f"\nSPEAKER_* всего: {speaker_total}")
    print(f"Guest* всего: {guest_total}")

    print("\nДетализация:")
    for typ, cnt in sorted(type_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {typ}: {cnt}")

    # === АНАЛИЗ КОНТЕКСТА ===
    print("\n=== АНАЛИЗ КОНТЕКСТА НЕРАСПОЗНАННЫХ ===")

    # Причины нераспознавания
    no_context = 0
    short_context = 0
    no_name_patterns = 0
    has_potential_name = 0

    name_patterns = [
        r'(?:его|её|ее)?\s*зовут\s+([А-ЯЁ][а-яё]+)',
        r'(?:здравствуй(?:те)?|привет),?\s+([А-ЯЁ][а-яё]+)',
        r'(?:наш\s+)?гость\s+([А-ЯЁ][а-яё]+)',
        r'(?:у\s+нас|с\s+нами)\s+([А-ЯЁ][а-яё]+)',
        r'[Мм]еня\s+зовут\s+([А-ЯЁ][а-яё]+)',
    ]

    potential_names = []

    for g in unidentified:
        context = g.get('context', [])
        first_lines = g.get('first_lines', [])

        if not context and not first_lines:
            no_context += 1
            continue

        if len(context) < 3 and len(first_lines) < 2:
            short_context += 1
            continue

        # Ищем паттерны имён
        all_text = ' '.join(context + first_lines)
        found_name = False
        for pattern in name_patterns:
            match = re.search(pattern, all_text)
            if match:
                potential_names.append({
                    'episode': g['episode'],
                    'guest_id': g['guest_id'],
                    'potential_name': match.group(1),
                    'pattern': pattern[:30]
                })
                found_name = True
                break

        if found_name:
            has_potential_name += 1
        else:
            no_name_patterns += 1

    print(f"Без контекста: {no_context}")
    print(f"Короткий контекст (<3 реплик): {short_context}")
    print(f"Нет паттернов имён: {no_name_patterns}")
    print(f"Есть потенциальные имена (пропущены): {has_potential_name}")

    # === ВЫПУСКИ С НАИБОЛЬШИМ ЧИСЛОМ НЕРАСПОЗНАННЫХ ===
    print("\n=== ВЫПУСКИ С НАИБОЛЬШИМ ЧИСЛОМ НЕРАСПОЗНАННЫХ ===")

    episodes_unidentified = Counter(g['episode'] for g in unidentified)
    for ep, cnt in episodes_unidentified.most_common(15):
        guests = [g['guest_id'] for g in unidentified if g['episode'] == ep]
        print(f"  Выпуск {ep}: {cnt} ({', '.join(guests[:5])}{'...' if len(guests) > 5 else ''})")

    # === АНАЛИЗ SPEAKER_99 ===
    print("\n=== АНАЛИЗ SPEAKER_99 ===")

    speaker_99 = [g for g in unidentified if g['guest_id'] == 'SPEAKER_99']
    print(f"Всего SPEAKER_99: {len(speaker_99)}")

    # Типичный контент SPEAKER_99
    speaker_99_content = []
    for g in speaker_99[:50]:
        lines = g.get('first_lines', [])
        if lines:
            first_line = lines[0][:60]
            speaker_99_content.append(first_line)

    print("\nПримеры реплик SPEAKER_99:")
    for line in speaker_99_content[:10]:
        print(f"  «{line}...»")

    # === ПОТЕНЦИАЛЬНЫЕ ИМЕНА (ПРОПУЩЕННЫЕ) ===
    if potential_names:
        print(f"\n=== ПОТЕНЦИАЛЬНЫЕ ИМЕНА (ПРОПУЩЕНЫ СКРИПТАМИ) ===")
        print(f"Найдено {len(potential_names)} потенциальных имён:")

        # Группируем по имени
        name_groups = defaultdict(list)
        for p in potential_names:
            name_groups[p['potential_name']].append(p['episode'])

        for name, episodes in sorted(name_groups.items(), key=lambda x: -len(x[1]))[:20]:
            eps_str = ', '.join(map(str, episodes[:5]))
            print(f"  {name}: {len(episodes)} раз (выпуски: {eps_str})")

    # === СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ===
    stats = {
        'total_unidentified': len(unidentified),
        'by_type': {
            'SPEAKER_total': speaker_total,
            'Guest_total': guest_total,
            'details': dict(type_counts.most_common(20))
        },
        'context_analysis': {
            'no_context': no_context,
            'short_context': short_context,
            'no_name_patterns': no_name_patterns,
            'has_potential_name': has_potential_name
        },
        'top_episodes': dict(episodes_unidentified.most_common(20)),
        'potential_names': potential_names[:50]
    }

    with open('unidentified_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\nСтатистика сохранена в unidentified_stats.json")


if __name__ == '__main__':
    main()
