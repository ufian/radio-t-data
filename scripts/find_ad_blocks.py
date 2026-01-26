#!/usr/bin/env python3
"""
Находит рекламные блоки в эпизодах по паттернам:
1. Кластеры реплик Alek.sys (когда он не участник выпуска, а только читает рекламу)
2. Уже помеченные _ad сегменты (для определения границ)
3. Рекламные слова в тексте (V-Scale, Vscale, DigitalOcean, Тинькофф)

Выводит правила ad_time_range для добавления в конфиг.
"""

import json
from collections import defaultdict
from pathlib import Path


AD_KEYWORDS = [
    'v-scale', 'vscale', 'digitalocean', 'digital ocean',
    'тинькофф', 'tinkoff', 'vultr', 'fastvps', 'fast vps',
    'кэшбэк', 'кешбэк', 'cashback', 'облачн', 'хостинг',
    'спонсор', 'промокод', 'promo'
]


def is_ad_text(text: str) -> bool:
    """Проверяет содержит ли текст рекламные слова"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in AD_KEYWORDS)


def find_clusters(subs: list, author: str, max_gap: float = 60) -> list:
    """Находит кластеры реплик автора (группы с промежутками < max_gap)"""
    author_subs = [(s['stime'], s['etime'], s['text']) for s in subs if s.get('author') == author]
    if not author_subs:
        return []

    author_subs.sort()
    clusters = []
    current_cluster = [author_subs[0]]

    for i in range(1, len(author_subs)):
        prev_end = current_cluster[-1][1]
        curr_start = author_subs[i][0]

        if curr_start - prev_end <= max_gap:
            current_cluster.append(author_subs[i])
        else:
            clusters.append(current_cluster)
            current_cluster = [author_subs[i]]

    clusters.append(current_cluster)
    return clusters


def analyze_episode(episode: int, data_path: Path) -> list:
    """Анализирует эпизод и возвращает потенциальные рекламные блоки"""
    cc_file = data_path / str(episode) / f'{episode}_cc.json'
    if not cc_file.exists():
        return []

    with open(cc_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    subs = data.get('subs', [])
    results = []

    # Находим кластеры Alek.sys
    aleksys_clusters = find_clusters(subs, 'Alek.sys', max_gap=60)

    for cluster in aleksys_clusters:
        # Проверяем есть ли рекламные слова в кластере
        texts = ' '.join([c[2] for c in cluster])
        has_ad_words = is_ad_text(texts)

        # Кластер короткий (< 2 минут) и содержит рекламные слова
        cluster_start = cluster[0][0]
        cluster_end = cluster[-1][1]
        cluster_duration = cluster_end - cluster_start

        if has_ad_words and cluster_duration < 120:
            results.append({
                'episode': episode,
                'start': int(cluster_start) - 5,  # небольшой запас
                'end': int(cluster_end) + 5,
                'duration': cluster_duration,
                'reason': f'Alek.sys ad cluster ({len(cluster)} replies, {cluster_duration:.0f}s)',
                'sample_text': texts[:100]
            })

    # Находим _ad сегменты и расширяем их
    ad_subs = [(s['stime'], s['etime']) for s in subs if s.get('author') == '_ad']
    if ad_subs:
        ad_clusters = []
        ad_subs.sort()
        current = [ad_subs[0]]

        for i in range(1, len(ad_subs)):
            prev_end = current[-1][1]
            curr_start = ad_subs[i][0]

            if curr_start - prev_end <= 30:  # 30 сек gap для _ad
                current.append(ad_subs[i])
            else:
                ad_clusters.append(current)
                current = [ad_subs[i]]
        ad_clusters.append(current)

        # Проверяем есть ли не-_ad реплики внутри _ad кластеров
        for cluster in ad_clusters:
            cluster_start = cluster[0][0]
            cluster_end = cluster[-1][1]

            # Ищем реплики других авторов внутри этого диапазона
            others_inside = [s for s in subs
                           if s.get('author') not in ('_ad', '_artifact', 'SPEAKER_99')
                           and cluster_start <= s['stime'] <= cluster_end]

            if others_inside:
                results.append({
                    'episode': episode,
                    'start': int(cluster_start) - 2,
                    'end': int(cluster_end) + 2,
                    'duration': cluster_end - cluster_start,
                    'reason': f'Mixed _ad block with {len(others_inside)} other speakers',
                    'other_speakers': list(set(s['author'] for s in others_inside))
                })

    return results


def main():
    base_path = Path(__file__).resolve().parent.parent
    data_path = base_path / 'data_clean'  # Используем data_clean

    print("# Ad time range rules\n")
    print("rules:")

    all_rules = []

    # Анализируем все выпуски
    for episode in range(0, 1000):
        results = analyze_episode(episode, data_path)
        for r in results:
            all_rules.append(r)

    # Выводим уникальные правила
    seen = set()
    for r in sorted(all_rules, key=lambda x: (x['episode'], x['start'])):
        key = (r['episode'], r['start'], r['end'])
        if key in seen:
            continue
        seen.add(key)

        print(f"  - id: ad_range_e{r['episode']}_{r['start']}_{r['end']}")
        print(f"    type: ad_time_range")
        print(f"    episode: {r['episode']}")
        print(f"    time_range:")
        print(f"      start: {r['start']}")
        print(f"      end: {r['end']}")
        print(f"    reason: \"{r['reason']}\"")
        print()


if __name__ == '__main__':
    main()
