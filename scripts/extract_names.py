#!/usr/bin/env python3
"""
Извлечение имён неизвестных гостей из контекста
"""

import json
import re
from collections import defaultdict
from pathlib import Path


def normalize_author(author):
    """Нормализация имени автора"""
    if not author:
        return None
    author = author.strip()
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
    if re.match(r'^Guest(_?\d+)?$', author):
        return True
    if re.match(r'^SPEAKER_\d+$', author):
        return True
    return False


def should_exclude(author):
    """Проверка на исключаемых"""
    if not author:
        return True
    exclude_list = ['Unknown', 'GPT', 'ElevenLabs', '_ad', '_extra', '']
    if author in exclude_list:
        return True
    if is_unknown_guest(author):
        return True
    return False


def load_episode_cc(episode_num):
    """Загрузка субтитров"""
    cc_path = Path(f'data/{episode_num}/{episode_num}_cc.json')
    if not cc_path.exists():
        return None
    try:
        with open(cc_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('subs', [])
    except (json.JSONDecodeError, IOError):
        return None


def extract_name_from_context(context_lines, guest_first_lines):
    """
    Извлечение имени из контекста представления
    Возвращает (имя, метод_извлечения, исходная_строка)
    """

    # Валидные русские имена (наиболее частые)
    valid_russian_names = {
        # Мужские
        'Александр', 'Алексей', 'Андрей', 'Антон', 'Артём', 'Артем', 'Борис',
        'Вадим', 'Валентин', 'Валерий', 'Василий', 'Виктор', 'Виталий', 'Владимир',
        'Владислав', 'Вячеслав', 'Геннадий', 'Георгий', 'Григорий', 'Даниил', 'Денис',
        'Дмитрий', 'Евгений', 'Егор', 'Иван', 'Игорь', 'Илья', 'Кирилл', 'Константин',
        'Леонид', 'Максим', 'Михаил', 'Никита', 'Николай', 'Олег', 'Павел', 'Пётр', 'Петр',
        'Роман', 'Руслан', 'Сергей', 'Станислав', 'Степан', 'Тимофей', 'Фёдор', 'Федор',
        'Эдуард', 'Юрий', 'Ярослав',
        # Женские
        'Александра', 'Алёна', 'Алена', 'Алина', 'Анастасия', 'Анна', 'Валентина',
        'Валерия', 'Вера', 'Виктория', 'Галина', 'Дарья', 'Евгения', 'Екатерина',
        'Елена', 'Елизавета', 'Ирина', 'Ксения', 'Лариса', 'Людмила', 'Маргарита',
        'Марина', 'Мария', 'Надежда', 'Наталья', 'Нина', 'Оксана', 'Ольга', 'Полина',
        'Светлана', 'Софья', 'Татьяна', 'Юлия', 'Яна',
        # Уменьшительные
        'Саша', 'Саня', 'Шура', 'Лёша', 'Леша', 'Лёха', 'Андрюха', 'Антоха',
        'Вадик', 'Валера', 'Вася', 'Витя', 'Володя', 'Вова', 'Слава', 'Гена', 'Гоша',
        'Гриша', 'Даня', 'Денис', 'Дима', 'Митя', 'Женя', 'Егор', 'Ваня', 'Игорь',
        'Илюха', 'Кирюха', 'Костя', 'Лёня', 'Леня', 'Макс', 'Миша', 'Никита', 'Коля',
        'Олежа', 'Паша', 'Петя', 'Рома', 'Руся', 'Серёга', 'Серега', 'Стас', 'Стёпа',
        'Степа', 'Тима', 'Федя', 'Эдик', 'Юра', 'Ярик',
        'Алёнка', 'Алинка', 'Настя', 'Аня', 'Анюта', 'Валя', 'Лера', 'Верка', 'Вика',
        'Галя', 'Даша', 'Женечка', 'Катя', 'Лена', 'Лиза', 'Ира', 'Ксюша', 'Ксюше',
        'Лариска', 'Люда', 'Рита', 'Маринка', 'Маша', 'Машка', 'Надя', 'Наташа',
        'Нинка', 'Оксанка', 'Оля', 'Олька', 'Полинка', 'Света', 'Соня', 'Таня', 'Юля', 'Янка',
        # Иностранные частые
        'Майкл', 'Майк', 'Джон', 'Алекс', 'Макс', 'Стив', 'Марк', 'Том', 'Дэн', 'Бен',
    }

    # Паттерны для представления ведущим (в контексте ДО появления гостя)
    host_patterns = [
        # "зовут X", "его/её зовут X"
        (r'(?:его|её|ее|их)?\s*зовут\s+([А-ЯЁA-Z][а-яёa-z]+(?:\s+[А-ЯЁA-Z][а-яёa-z]+)?)', 'зовут'),
        # "представляю X", "представляю вам X"
        (r'представля[юем]\s+(?:вам\s+)?([А-ЯЁA-Z][а-яёa-z]+)', 'представляю'),
        # "здравствуй(те), X" / "привет, X"
        (r'(?:здравствуй(?:те)?|привет),?\s+([А-ЯЁA-Z][а-яёa-z]+)', 'приветствие'),
        # "наш гость X" / "гость в студии X"
        (r'(?:наш\s+)?гость(?:\s+в\s+студии)?\s+([А-ЯЁA-Z][а-яёa-z]+)', 'гость'),
        # "в студии X" / "у нас в студии X"
        (r'(?:у\s+нас\s+)?в\s+студии\s+([А-ЯЁA-Z][а-яёa-z]+)', 'в студии'),
        # "это X" - только с явным контекстом представления (третий гость это X, у нас это X)
        (r'(?:гость|участник|слушатель|звонящий|человек)\s+(?:[-–—]\s*)?это\s+([А-ЯЁA-Z][а-яёa-z]+)', 'это гость'),
        # "а это X" / "и это X" в контексте представления
        (r'(?:а|и)\s+это\s+([А-ЯЁA-Z][а-яёa-z]+)(?:\s+из|\s+с\s+нами|,)', 'а это'),
        # "подключился X" / "подключается X"
        (r'подключ(?:ился|ается|аемся)\s+([А-ЯЁA-Z][а-яёa-z]+)', 'подключился'),
        # "слово X" / "даём слово X"
        (r'(?:да(?:й|ём|ю|м)?\s+)?слово\s+([А-ЯЁA-Z][а-яёa-z]+)', 'слово'),
        # Ники/юзернеймы в контексте представления
        (r'известн(?:ый|ая)\s+(?:как|под\s+ником)\s+([A-Za-z][A-Za-z0-9_]+)', 'известный как'),
        (r'(?:он|она)\s+же\s+([A-Za-z][A-Za-z0-9_]+)', 'он же'),
        # "звонит X" / "позвонил X"
        (r'(?:звонит|позвонил[аи]?)\s+([А-ЯЁA-Z][а-яёa-z]+)', 'звонит'),
        # "пишет X" / "написал X"
        (r'(?:пишет|написал[аи]?)\s+([А-ЯЁA-Z][а-яёa-z]+)', 'пишет'),
        # "спрашивает X"
        (r'спрашивает\s+([А-ЯЁA-Z][а-яёa-z]+)', 'спрашивает'),
        # "с нами X" / "у нас X"
        (r'(?:с\s+нами|у\s+нас)\s+([А-ЯЁA-Z][а-яёa-z]+)', 'с нами'),
        # "присоединился X"
        (r'присоедин(?:ился|яется)\s+([А-ЯЁA-Z][а-яёa-z]+)', 'присоединился'),
    ]

    # Паттерны для самопредставления гостя (в первых репликах)
    self_patterns = [
        # "Меня зовут X"
        (r'[Мм]еня\s+зовут\s+([А-ЯЁA-Z][а-яёa-z]+)', 'самопредставление'),
        # "Я - X" / "Я X"
        (r'^[Яя]\s+[-–—]?\s*([А-ЯЁA-Z][а-яёa-z]+)', 'я'),
        # Ник в начале: "Username тут"
        (r'^([A-Za-z][A-Za-z0-9_]+)\s+(?:тут|здесь|на связи)', 'ник'),
    ]

    # Стоп-слова (не имена) - расширенный список
    stop_words = {
        # Частицы и междометия
        'Да', 'Нет', 'Ну', 'Вот', 'Так', 'Это', 'Там', 'Тут', 'Здесь', 'Очень',
        'Ага', 'Угу', 'Ого', 'Ух', 'Эх', 'Ой', 'Ай', 'Эй', 'Хм', 'Ммм',
        # Приветствия
        'Привет', 'Здравствуйте', 'Здравствуй', 'Спасибо', 'Пожалуйста',
        'Хорошо', 'Отлично', 'Прекрасно', 'Замечательно', 'Великолепно',
        # Время
        'Сегодня', 'Завтра', 'Вчера', 'Потом', 'Сейчас', 'Теперь', 'Тогда',
        # Наречия и вводные
        'Просто', 'Конечно', 'Наверное', 'Возможно', 'Действительно', 'Вообще',
        'Слушай', 'Смотри', 'Знаешь', 'Понимаешь', 'Короче', 'Кстати', 'Правда',
        # Прилагательные/местоимения
        'Добрый', 'Доброе', 'Доброго', 'Дорогой', 'Дорогая', 'Дорогие',
        'Guest', 'Гость', 'Третий', 'Четвёртый', 'Пятый', 'Шестой',
        'Новый', 'Новая', 'Первый', 'Второй', 'Наш', 'Ваш', 'Мой', 'Твой',
        'Какой', 'Какая', 'Какое', 'Какие', 'Такой', 'Такая', 'Такое', 'Такие',
        'Который', 'Которая', 'Которое', 'Которые',
        # Глаголы и отглагольные
        'Как', 'Что', 'Где', 'Когда', 'Почему', 'Зачем', 'Куда', 'Откуда',
        'Сказать', 'Говорить', 'Делать', 'Быть', 'Было', 'Будет', 'Есть',
        'Называется', 'Получается', 'Оказывается', 'Кажется',
        # Прочие частые слова
        'Все', 'Всё', 'Раз', 'Еще', 'Ещё', 'Уже', 'Дело', 'Время', 'Нормально',
        'Правильно', 'Интересно', 'Странно', 'Понятно', 'Ладно', 'Давай',
    }

    def is_valid_name(name):
        """Проверка что строка похожа на имя"""
        if not name or len(name) < 3:
            return False

        first_word = name.split()[0]

        # Стоп-слова
        if first_word in stop_words or first_word.lower() in {w.lower() for w in stop_words}:
            return False

        # Точное совпадение с известными именами
        if first_word in valid_russian_names:
            return True

        # Проверка на имя-отчество (два слова с заглавной)
        words = name.split()
        if len(words) == 2 and all(w[0].isupper() for w in words):
            if words[0] in valid_russian_names:
                return True

        # Проверка на никнейм (латиница, начинается с буквы)
        if re.match(r'^[A-Za-z][A-Za-z0-9_.-]+$', first_word) and len(first_word) > 3:
            # Исключаем общие слова и короткие
            common_words = {'Google', 'Apple', 'Microsoft', 'Facebook', 'Twitter', 'Youtube',
                           'Linux', 'Windows', 'Android', 'iPhone', 'Radio', 'Podcast',
                           'Amazon', 'Netflix', 'Spotify', 'Telegram', 'Skype', 'Zoom',
                           'Instagram', 'WhatsApp', 'Chrome', 'Firefox', 'Safari',
                           'the', 'The', 'big', 'Big', 'new', 'New', 'all', 'All'}
            if first_word not in common_words and len(first_word) >= 4:
                return True

        return False

    # Ищем в контексте (последние строки важнее)
    for line in reversed(context_lines):
        # Убираем префикс автора
        if ': ' in line:
            text = line.split(': ', 1)[1]
        else:
            text = line

        for pattern, method in host_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if is_valid_name(name):
                    return (name, method, line)

    # Ищем в первых репликах гостя
    for line in guest_first_lines[:2]:  # Только первые 2 реплики
        for pattern, method in self_patterns:
            match = re.search(pattern, line)
            if match:
                name = match.group(1).strip()
                if is_valid_name(name):
                    return (name, method, line)

    return (None, None, None)


def extract_nickname_from_context(context_lines, guest_first_lines):
    """
    Извлечение никнейма/username из контекста
    """
    # Исключаемые слова (бренды, компании и т.п.)
    excluded_nicks = {
        'Google', 'Apple', 'Microsoft', 'Facebook', 'Twitter', 'Youtube', 'YouTube',
        'Linux', 'Windows', 'Android', 'iPhone', 'Radio', 'Podcast',
        'Amazon', 'Netflix', 'Spotify', 'Telegram', 'Skype', 'Zoom',
        'Instagram', 'WhatsApp', 'Chrome', 'Firefox', 'Safari',
        'Github', 'GitHub', 'Bitbucket', 'Docker', 'Kubernetes',
        'Python', 'JavaScript', 'TypeScript', 'Java', 'Ruby', 'Rust', 'Golang',
        'Reddit', 'Habr', 'Medium', 'Stack', 'Overflow',
    }

    def is_valid_nick(nick):
        if not nick or len(nick) < 4:
            return False
        if nick in excluded_nicks:
            return False
        # Должен содержать хотя бы одну букву
        if not re.search(r'[A-Za-z]', nick):
            return False
        return True

    nick_patterns = [
        # Ники латиницей
        (r'(?:известн(?:ый|ая)\s+как|под\s+ником|он\s+же|она\s+же)\s+([A-Za-z][A-Za-z0-9_.-]+)', 'ник'),
        (r'(?:это|наш|гость)\s+([A-Za-z][A-Za-z0-9_]+)(?:\s|,|\.)', 'ник прямой'),
        # Пользователь X
        (r'пользовател[ья]\s+([A-Za-z][A-Za-z0-9_]+)', 'пользователь'),
        # @username
        (r'@([A-Za-z][A-Za-z0-9_]+)', 'twitter'),
    ]

    # В контексте
    for line in reversed(context_lines):
        if ': ' in line:
            text = line.split(': ', 1)[1]
        else:
            text = line

        for pattern, method in nick_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                nick = match.group(1).strip()
                if is_valid_nick(nick):
                    return (nick, method, line)

    # В первых репликах
    for line in guest_first_lines[:2]:
        # "Я пингвинатор" и подобные
        match = re.search(r'^(?:Я|Ну\s+я|Это)\s+([A-Za-z][A-Za-z0-9_]+|[А-ЯЁа-яё]+атор|[А-ЯЁа-яё]+ер)', line, re.IGNORECASE)
        if match:
            nick = match.group(1).strip()
            if len(nick) > 3:
                return (nick, 'самоназвание', line)

    return (None, None, None)


def main():
    print("Извлечение имён неизвестных гостей...\n")

    # Результаты
    identified_guests = []  # (episode, guest_id, name, method, source_line)
    unidentified_guests = []  # (episode, guest_id, context_preview)

    episodes_with_identified = set()
    episodes_with_unidentified = set()

    for episode_num in range(0, 992):
        subs = load_episode_cc(episode_num)
        if not subs:
            continue

        # Находим неизвестных гостей
        unknown_authors = set()
        for sub in subs:
            author = normalize_author(sub.get('author', ''))
            if is_unknown_guest(author):
                unknown_authors.add(author)

        # Для каждого неизвестного гостя пытаемся найти имя
        for unknown_author in unknown_authors:
            # Пропускаем SPEAKER_* с короткими репликами
            if unknown_author.startswith('SPEAKER_'):
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

            # Контекст: 20 реплик до
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

            # Пытаемся извлечь имя
            name, method, source = extract_name_from_context(context_lines, guest_lines)

            # Если имя не найдено, пробуем никнейм
            if not name:
                name, method, source = extract_nickname_from_context(context_lines, guest_lines)

            if name:
                identified_guests.append((episode_num, unknown_author, name, method, source))
                episodes_with_identified.add(episode_num)
            else:
                # Сохраняем превью контекста для анализа
                context_preview = context_lines[-3:] if context_lines else []
                unidentified_guests.append((episode_num, unknown_author, context_preview, guest_lines[:2]))
                episodes_with_unidentified.add(episode_num)

    # Статистика
    total_guests = len(identified_guests) + len(unidentified_guests)
    total_episodes = len(episodes_with_identified | episodes_with_unidentified)

    print(f"=== СТАТИСТИКА ===")
    print(f"Всего неизвестных гостей (без рекламы/джинглов): {total_guests}")
    print(f"Идентифицировано: {len(identified_guests)} ({len(identified_guests)*100//total_guests}%)")
    print(f"Не идентифицировано: {len(unidentified_guests)}")
    print()
    print(f"Выпусков с неизвестными: {total_episodes}")
    print(f"Выпусков с идентификацией: {len(episodes_with_identified)}")
    print(f"Выпусков без идентификации: {len(episodes_with_unidentified - episodes_with_identified)}")
    print()

    # Методы извлечения
    methods = defaultdict(int)
    for _, _, _, method, _ in identified_guests:
        methods[method] += 1

    print("=== МЕТОДЫ ИЗВЛЕЧЕНИЯ ===")
    for method, count in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"  {method}: {count}")
    print()

    # Сохраняем результаты
    with open('identified_guests.md', 'w', encoding='utf-8') as f:
        f.write('# Идентифицированные гости\n\n')
        f.write('| Выпуск | Гость | Имя | Метод | Источник |\n')
        f.write('|--------|-------|-----|-------|----------|\n')

        for ep, guest_id, name, method, source in sorted(identified_guests):
            source_short = source[:60] + '...' if source and len(source) > 60 else source
            source_escaped = source_short.replace('|', '\\|') if source_short else ''
            f.write(f'| {ep} | {guest_id} | **{name}** | {method} | {source_escaped} |\n')

    print(f"Сохранено: identified_guests.md")

    # Сохраняем неидентифицированных для ручного анализа
    with open('unidentified_guests.md', 'w', encoding='utf-8') as f:
        f.write('# Неидентифицированные гости\n\n')
        f.write('Требуется ручной анализ контекста.\n\n')

        current_ep = None
        for ep, guest_id, context, first_lines in sorted(unidentified_guests):
            if ep != current_ep:
                f.write(f'\n## Выпуск {ep}\n\n')
                current_ep = ep

            f.write(f'### {guest_id}\n\n')
            if context:
                f.write('**Контекст:**\n```\n')
                for line in context:
                    f.write(f'{line}\n')
                f.write('```\n\n')
            if first_lines:
                f.write('**Первые реплики:**\n```\n')
                for line in first_lines:
                    f.write(f'{line}\n')
                f.write('```\n\n')

    print(f"Сохранено: unidentified_guests.md")

    # Топ-20 идентифицированных имён
    print("\n=== ТОП-20 ИДЕНТИФИЦИРОВАННЫХ ИМЁН ===")
    name_counts = defaultdict(list)
    for ep, guest_id, name, method, _ in identified_guests:
        name_counts[name.lower()].append((ep, name))

    for name_lower, occurrences in sorted(name_counts.items(), key=lambda x: -len(x[1]))[:20]:
        display_name = occurrences[0][1]  # Берём первое написание
        eps = [str(o[0]) for o in occurrences[:5]]
        eps_str = ', '.join(eps) + ('...' if len(occurrences) > 5 else '')
        print(f"  {display_name}: {len(occurrences)} раз (выпуски: {eps_str})")


if __name__ == '__main__':
    main()
