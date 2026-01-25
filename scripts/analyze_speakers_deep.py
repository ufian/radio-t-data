#!/usr/bin/env python3
"""
Глубокий анализ SPEAKER_* — определяем, кто это на самом деле
"""

import json
import re
from pathlib import Path
from collections import Counter, defaultdict


def load_json_safe(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def analyze_speaker_content(guest):
    """Анализирует контент SPEAKER_* для определения типа"""
    first_lines = guest.get('first_lines', [])
    context = guest.get('context', [])
    guest_id = guest.get('guest_id', '')

    all_text = ' '.join(first_lines).lower()

    # Признаки рекламы/джингла
    ad_keywords = ['реклама', 'спонсор', 'поддержк', 'промокод', 'скидк', 'акци',
                   'подписывайтесь', 'канал', 'ссылк', 'описани']
    if any(kw in all_text for kw in ad_keywords):
        return 'реклама/промо'

    # Признаки технического контента (чтение новостей, цитат)
    if re.search(r'(согласно|по данным|сообщает|пишет|заявил)', all_text):
        return 'цитата/новость'

    # Признаки гостя - самопредставление
    if re.search(r'(меня зовут|я из|работаю в|занимаюсь)', all_text):
        return 'реальный гость'

    # Короткие реплики без контекста представления
    if len(all_text) < 100:
        # Проверяем контекст на предмет представления
        context_text = ' '.join(context).lower()
        if not re.search(r'(гость|звонит|подключ|представ|зовут)', context_text):
            return 'неатрибутированный спикер'

    # Если есть длинные осмысленные реплики
    if len(all_text) > 200:
        return 'вероятно гость'

    return 'неопределённый'


def main():
    # Загружаем реальных нераспознанных
    real_unidentified = load_json_safe('real_unidentified_guests.json')
    print(f"Реальных нераспознанных: {len(real_unidentified)}")

    # Разделяем на SPEAKER_* и Guest*
    speakers = [g for g in real_unidentified if g['guest_id'].startswith('SPEAKER_')]
    guests = [g for g in real_unidentified if 'Guest' in g['guest_id']]

    print(f"SPEAKER_*: {len(speakers)}")
    print(f"Guest*: {len(guests)}")

    # Анализируем SPEAKER_*
    print(f"\n=== АНАЛИЗ SPEAKER_* ===")

    speaker_types = Counter()
    speakers_by_type = defaultdict(list)

    for s in speakers:
        stype = analyze_speaker_content(s)
        speaker_types[stype] += 1
        speakers_by_type[stype].append(s)

    for stype, cnt in speaker_types.most_common():
        print(f"  {stype}: {cnt}")

    # Примеры каждого типа
    print(f"\n=== ПРИМЕРЫ ПО ТИПАМ ===")
    for stype in ['реклама/промо', 'цитата/новость', 'реальный гость', 'неатрибутированный спикер']:
        examples = speakers_by_type.get(stype, [])[:3]
        if examples:
            print(f"\n{stype.upper()}:")
            for ex in examples:
                first = ex['first_lines'][0][:70] if ex['first_lines'] else ''
                print(f"  Выпуск {ex['episode']}: «{first}...»")

    # Фильтруем - оставляем только реальных гостей и вероятных гостей
    real_guests_filtered = []

    # Guest* - все оставляем
    real_guests_filtered.extend(guests)

    # SPEAKER_* - только "реальный гость" и "вероятно гость"
    for s in speakers:
        stype = analyze_speaker_content(s)
        if stype in ('реальный гость', 'вероятно гость'):
            real_guests_filtered.append(s)

    print(f"\n=== ПОСЛЕ ГЛУБОКОЙ ФИЛЬТРАЦИИ ===")
    print(f"Реальные нераспознанные гости: {len(real_guests_filtered)}")

    # Статистика по типам
    type_counts = Counter()
    for g in real_guests_filtered:
        if g['guest_id'].startswith('SPEAKER_'):
            type_counts['SPEAKER_* (вероятные гости)'] += 1
        else:
            type_counts['Guest*'] += 1

    for typ, cnt in type_counts.most_common():
        print(f"  {typ}: {cnt}")

    # Выпуски
    print(f"\n=== ВЫПУСКИ С РЕАЛЬНЫМИ НЕРАСПОЗНАННЫМИ ===")
    episodes = Counter(g['episode'] for g in real_guests_filtered)
    for ep, cnt in episodes.most_common(20):
        guests_list = [g['guest_id'] for g in real_guests_filtered if g['episode'] == ep]
        print(f"  Выпуск {ep}: {cnt} ({', '.join(guests_list[:3])})")

    # Сохраняем
    with open('final_unidentified_guests.json', 'w', encoding='utf-8') as f:
        json.dump(real_guests_filtered, f, ensure_ascii=False, indent=2)

    # Markdown
    with open('final_unidentified_guests.md', 'w', encoding='utf-8') as f:
        f.write('# Финальный список нераспознанных гостей\n\n')
        f.write('После фильтрации шума, технических артефактов и неатрибутированных спикеров.\n\n')
        f.write(f'**Всего:** {len(real_guests_filtered)} гостей\n\n')

        by_episode = defaultdict(list)
        for g in real_guests_filtered:
            by_episode[g['episode']].append(g)

        for ep in sorted(by_episode.keys()):
            ep_guests = by_episode[ep]
            f.write(f'## Выпуск {ep}\n\n')
            for g in ep_guests:
                f.write(f"### {g['guest_id']}\n\n")
                if g.get('context'):
                    f.write('**Контекст:**\n```\n')
                    for line in g['context'][-5:]:
                        f.write(f'{line}\n')
                    f.write('```\n\n')
                if g.get('first_lines'):
                    f.write('**Реплики:**\n```\n')
                    for line in g['first_lines'][:3]:
                        f.write(f'{line}\n')
                    f.write('```\n\n')

    print(f"\nСохранено:")
    print(f"  - final_unidentified_guests.json")
    print(f"  - final_unidentified_guests.md")

    # Итоговая статистика
    identified = load_json_safe('all_identified_guests.json')
    total_identified = len(identified)
    total_real_unidentified = len(real_guests_filtered)

    print(f"\n=== ФИНАЛЬНАЯ СТАТИСТИКА ===")
    print(f"Идентифицировано: {total_identified}")
    print(f"Реальные нераспознанные: {total_real_unidentified}")
    print(f"Эффективность: {total_identified}/{total_identified + total_real_unidentified} = {total_identified*100//(total_identified + total_real_unidentified)}%")


if __name__ == '__main__':
    main()
