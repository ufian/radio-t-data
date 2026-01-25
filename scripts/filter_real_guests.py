#!/usr/bin/env python3
"""
Фильтрация нераспознанных: оставляем только реальных гостей
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


def is_real_dialogue(guest):
    """Проверяет, похожи ли реплики на реальный диалог"""
    first_lines = guest.get('first_lines', [])
    context = guest.get('context', [])
    guest_id = guest.get('guest_id', '')

    if not first_lines:
        return False, "нет реплик"

    # Объединяем все реплики гостя
    all_text = ' '.join(first_lines)
    total_len = len(all_text)

    # Слишком короткий текст
    if total_len < 20:
        return False, f"слишком короткий ({total_len} симв.)"

    # Междометия и короткие слова
    interjections = {
        'да', 'нет', 'ну', 'ох', 'ах', 'эх', 'угу', 'ага', 'ого', 'ой',
        'хм', 'ммм', 'эээ', 'ааа', 'так', 'вот', 'ладно', 'окей', 'ок',
        'привет', 'пока', 'алло', 'здравствуйте', 'спасибо',
    }

    # Проверяем первую реплику
    first_line = first_lines[0].lower().strip()
    first_words = re.findall(r'[а-яёa-z]+', first_line)

    # Если первая реплика - только междометия
    if first_words and all(w in interjections for w in first_words[:3]) and len(first_line) < 30:
        # Проверяем остальные реплики
        if len(first_lines) < 2 or len(' '.join(first_lines[1:])) < 30:
            return False, "только междометия"

    # Технические артефакты
    tech_patterns = [
        r'^[\d\.\,\%\$\€]+$',  # Только цифры
        r'^[A-Z]{2,}$',  # Только аббревиатуры
        r'^\W+$',  # Только символы
        r'^https?://',  # URL
    ]
    for pattern in tech_patterns:
        if re.match(pattern, first_line):
            return False, "технический артефакт"

    # SPEAKER_99 требует более строгой проверки
    if guest_id == 'SPEAKER_99':
        # Должен быть достаточно длинный осмысленный текст
        if total_len < 50:
            return False, "SPEAKER_99 короткий"
        # Должны быть предложения
        if not re.search(r'[а-яёa-z]{4,}', all_text.lower()):
            return False, "SPEAKER_99 без слов"

    # Проверяем на осмысленность - должны быть слова длиннее 3 букв
    real_words = re.findall(r'[а-яёa-z]{4,}', all_text.lower())
    if len(real_words) < 2:
        return False, "мало осмысленных слов"

    return True, "похоже на диалог"


def main():
    # Загружаем данные
    all_guests = load_json_safe('guests_to_analyze.json')
    identified = load_json_safe('all_identified_guests.json')
    identified_keys = {(r['episode'], r['guest_id']) for r in identified}

    print(f"Всего гостей: {len(all_guests)}")
    print(f"Уже идентифицировано: {len(identified_keys)}")

    # Находим нераспознанных
    unidentified = []
    for g in all_guests:
        key = (g['episode'], g['guest_id'])
        if key not in identified_keys:
            unidentified.append(g)

    print(f"Нераспознано: {len(unidentified)}")

    # Фильтруем
    real_guests = []
    filtered_out = []
    filter_reasons = Counter()

    for g in unidentified:
        is_real, reason = is_real_dialogue(g)
        if is_real:
            real_guests.append(g)
        else:
            filtered_out.append({**g, 'filter_reason': reason})
            filter_reasons[reason] += 1

    print(f"\n=== РЕЗУЛЬТАТЫ ФИЛЬТРАЦИИ ===")
    print(f"Реальные гости (требуют внимания): {len(real_guests)}")
    print(f"Отфильтровано (не диалог): {len(filtered_out)}")

    print(f"\n=== ПРИЧИНЫ ФИЛЬТРАЦИИ ===")
    for reason, cnt in filter_reasons.most_common():
        print(f"  {reason}: {cnt}")

    # Статистика по реальным гостям
    print(f"\n=== СТАТИСТИКА РЕАЛЬНЫХ НЕРАСПОЗНАННЫХ ===")

    type_counts = Counter()
    for g in real_guests:
        guest_id = g['guest_id']
        if guest_id.startswith('SPEAKER_'):
            num = guest_id.replace('SPEAKER_', '')
            if num == '99':
                type_counts['SPEAKER_99'] += 1
            else:
                type_counts['SPEAKER_00-08'] += 1
        elif 'Guest' in guest_id:
            type_counts['Guest*'] += 1
        else:
            type_counts[guest_id] += 1

    for typ, cnt in type_counts.most_common():
        print(f"  {typ}: {cnt}")

    # Выпуски с реальными нераспознанными
    print(f"\n=== ВЫПУСКИ С РЕАЛЬНЫМИ НЕРАСПОЗНАННЫМИ ===")
    episodes = Counter(g['episode'] for g in real_guests)
    for ep, cnt in episodes.most_common(15):
        guests = [g['guest_id'] for g in real_guests if g['episode'] == ep]
        print(f"  Выпуск {ep}: {cnt} ({', '.join(guests[:4])})")

    # Примеры реальных нераспознанных
    print(f"\n=== ПРИМЕРЫ РЕАЛЬНЫХ НЕРАСПОЗНАННЫХ ===")
    for g in real_guests[:10]:
        first_line = g['first_lines'][0][:80] if g['first_lines'] else ''
        print(f"  Выпуск {g['episode']}, {g['guest_id']}: «{first_line}...»")

    # Сохраняем результаты
    with open('real_unidentified_guests.json', 'w', encoding='utf-8') as f:
        json.dump(real_guests, f, ensure_ascii=False, indent=2)

    # Создаём markdown отчёт
    with open('real_unidentified_guests.md', 'w', encoding='utf-8') as f:
        f.write('# Реальные нераспознанные гости\n\n')
        f.write(f'Гости с осмысленными репликами, которых не удалось идентифицировать.\n\n')
        f.write(f'**Всего:** {len(real_guests)}\n\n')

        # Группируем по выпускам
        by_episode = defaultdict(list)
        for g in real_guests:
            by_episode[g['episode']].append(g)

        for ep in sorted(by_episode.keys()):
            guests = by_episode[ep]
            f.write(f'## Выпуск {ep}\n\n')
            for g in guests:
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
    print(f"  - real_unidentified_guests.json ({len(real_guests)} записей)")
    print(f"  - real_unidentified_guests.md")

    # Итоговая статистика
    total_original = len(all_guests)
    total_identified = len(identified_keys)
    total_real_unidentified = len(real_guests)
    total_noise = len(filtered_out)

    print(f"\n=== ИТОГОВАЯ СТАТИСТИКА ===")
    print(f"Всего записей в данных: {total_original}")
    print(f"Идентифицировано: {total_identified} ({total_identified*100//total_original}%)")
    print(f"Реальные нераспознанные: {total_real_unidentified} ({total_real_unidentified*100//total_original}%)")
    print(f"Шум/артефакты: {total_noise} ({total_noise*100//total_original}%)")
    print(f"\nЭффективность идентификации (без шума): {total_identified}/{total_identified+total_real_unidentified} = {total_identified*100//(total_identified+total_real_unidentified)}%")


if __name__ == '__main__':
    main()
