# {{ batch_id }}

## Описание

{{ description }}

**Статус:** {{ status }}
**Записей для проверки:** {{ entries_count }}

## Задачи

- [ ] Прослушать контекст для каждой записи
- [ ] Определить реального спикера
- [ ] Заполнить `decision` в файле `batches/batch_{{ batch_id }}.yaml`
- [ ] Создать Pull Request

## Записи для проверки

| # | Выпуск | Время | Текст | Предложение |
|---|--------|-------|-------|-------------|
{% for entry in entries %}
| {{ loop.index }} | [{{ entry.episode }}]({{ entry.audio_url }}) | {{ entry.timestamp }} ({{ entry.duration_sec }}с) | {{ entry.text[:40] }}... | ? |
{% endfor %}

## Как помочь

### 1. Прослушать аудио

Кликните на номер выпуска в таблице выше — откроется аудио с нужного таймкода.

Или скачайте файл:
```
https://cdn.radio-t.com/rt_podcastXXX.mp3
```

### 2. Определить спикера

Прослушайте 10-15 секунд контекста и определите, кто на самом деле говорит эту реплику.

### 3. Заполнить решение в YAML

Откройте файл `cleaning/batches/batch_{{ batch_id }}.yaml` и заполните поле `decision`:

```yaml
decision:
  person_id: "bobuk"          # ID из people.yaml
  verified_by: "ваш_github"   # Ваш GitHub username
  comment: "Это реплика Бобука, не гостя"
```

### Доступные person_id

**Ведущие:**
- `umputun` — Umputun
- `bobuk` — Bobuk (Григорий Бакунов)
- `gray` — Gray
- `ksenks` — Ksenks (Ксения)
- `alek_sys` — Alek.sys (Алексей)

**Гости:**
- `eldar_murtazin` — EldarMurtazin (Эльдар Муртазин)
- `petr_didenko` — PetrDidenko (Пётр Диденко)
- и другие из `people.yaml`

### 4. Создать Pull Request

```bash
git checkout -b fix/batch-{{ batch_id }}
git add cleaning/batches/batch_{{ batch_id }}.yaml
git commit -m "Verify batch {{ batch_id }}"
git push origin fix/batch-{{ batch_id }}
```

## Контекст записей

{% for entry in entries %}
### {{ loop.index }}. Выпуск {{ entry.episode }} — {{ entry.timestamp }}

**Автор:** {{ entry.author }}
**Длительность:** {{ entry.duration_sec }} сек
**Аудио:** [{{ entry.audio_url }}]({{ entry.audio_url }})

**Контекст до:**
{% for ctx in entry.context_before %}
> {{ ctx }}
{% endfor %}

**Текст:**
> {{ entry.text }}

---
{% endfor %}

## После проверки

После того как все записи будут проверены:
1. Измените `status: "completed"` в YAML файле
2. Добавьте `verified_at: "YYYY-MM-DD"`
3. Создайте PR

---

*Этот issue создан автоматически скриптом `generate_batches.py`*
