#!/usr/bin/env python3
"""
Добавление таймстемпов к нераспознанным гостям для ручной верификации
"""

import json
import re
from pathlib import Path
from collections import defaultdict


def load_json_safe(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def format_time(seconds):
    """Конвертирует секунды в HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def normalize_author(author):
    if not author:
        return None
    author = author.strip()
    variations = {
        'Grey': 'Gray', ' Gray': 'Gray',
        'Alex.sys': 'Alek.sys', ' Umputun': 'Umputun',
    }
    return variations.get(author, author)


def load_episode_cc(episode_num):
    cc_path = Path(f'data/{episode_num}/{episode_num}_cc.json')
    if not cc_path.exists():
        return None
    try:
        with open(cc_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('subs', [])
    except:
        return None


def load_episode_desc(episode_num):
    """Загружает описание эпизода для получения URL аудио"""
    desc_path = Path(f'data/{episode_num}/{episode_num}_desc.json')
    if not desc_path.exists():
        return None
    try:
        with open(desc_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def main():
    # Загружаем нераспознанных гостей
    unidentified = load_json_safe('final_unidentified_guests.json')
    print(f"Загружено {len(unidentified)} нераспознанных гостей")

    # Добавляем таймстемпы
    enriched = []

    for guest in unidentified:
        episode_num = guest['episode']
        guest_id = guest['guest_id']

        # Загружаем данные эпизода
        subs = load_episode_cc(episode_num)
        desc = load_episode_desc(episode_num)

        if not subs:
            enriched.append(guest)
            continue

        # Находим первое появление гостя
        first_time = None
        for sub in subs:
            if normalize_author(sub.get('author')) == guest_id:
                first_time = sub.get('stime', 0)
                break

        # Добавляем информацию
        guest_enriched = {**guest}
        if first_time is not None:
            guest_enriched['timestamp_sec'] = first_time
            guest_enriched['timestamp'] = format_time(first_time)

        if desc:
            guest_enriched['audio_url'] = desc.get('audio', '')
            guest_enriched['episode_date'] = desc.get('date', '')

        enriched.append(guest_enriched)

    # Сохраняем обновлённый JSON
    with open('final_unidentified_guests.json', 'w', encoding='utf-8') as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    print(f"Обновлено: final_unidentified_guests.json")

    # Создаём улучшенный Markdown
    with open('final_unidentified_guests.md', 'w', encoding='utf-8') as f:
        f.write('# Нераспознанные гости подкаста Радио-Т\n\n')
        f.write('Гости с осмысленными репликами, которых не удалось идентифицировать автоматически.\n')
        f.write('Для каждого указан таймстемп первого появления для ручной верификации.\n\n')
        f.write(f'**Всего:** {len(enriched)} гостей\n\n')
        f.write('---\n\n')

        # Группируем по выпускам
        by_episode = defaultdict(list)
        for g in enriched:
            by_episode[g['episode']].append(g)

        for ep in sorted(by_episode.keys()):
            ep_guests = by_episode[ep]
            first_guest = ep_guests[0]

            # Заголовок выпуска с датой
            date_str = first_guest.get('episode_date', '')
            f.write(f'## Выпуск {ep}')
            if date_str:
                f.write(f' ({date_str})')
            f.write('\n\n')

            # Ссылка на аудио
            audio_url = first_guest.get('audio_url', '')
            if audio_url:
                f.write(f'🎧 [Аудио]({audio_url})\n\n')

            for g in ep_guests:
                ts = g.get('timestamp', '?')
                ts_sec = g.get('timestamp_sec', 0)

                f.write(f"### {g['guest_id']} @ {ts}\n\n")

                # Ссылка с таймкодом (если есть URL)
                if audio_url and ts_sec:
                    # Для CDN обычно можно добавить #t=XXX
                    f.write(f'⏱️ Перейти к [{ts}]({audio_url}#t={int(ts_sec)})\n\n')

                if g.get('context'):
                    f.write('**Контекст (до появления):**\n```\n')
                    for line in g['context'][-5:]:
                        f.write(f'{line}\n')
                    f.write('```\n\n')

                if g.get('first_lines'):
                    f.write('**Первые реплики:**\n```\n')
                    for line in g['first_lines'][:3]:
                        f.write(f'{line}\n')
                    f.write('```\n\n')

                f.write('---\n\n')

    print(f"Обновлено: final_unidentified_guests.md")

    # Краткая сводка
    print(f"\n=== СВОДКА ===")
    print(f"Выпусков с нераспознанными: {len(by_episode)}")

    # Примеры
    print(f"\n=== ПРИМЕРЫ С ТАЙМСТЕМПАМИ ===")
    for g in enriched[:10]:
        ts = g.get('timestamp', '?')
        first_line = g['first_lines'][0][:50] if g.get('first_lines') else ''
        print(f"  Выпуск {g['episode']} @ {ts} ({g['guest_id']}): «{first_line}...»")


if __name__ == '__main__':
    main()
