import json
import re

# Load all batch files
batches = []
for i in range(30, 40):
    with open(f'/Users/ufian/projects/experiment/batch_{i:03d}.json', 'r', encoding='utf-8') as f:
        batches.extend(json.load(f))

results = []

# Known hosts and common words to exclude
known_hosts = {
    "Umputun", "Bobuk", "Gray", "Ksenks", "Marin_k_a", "Alek.sys", 
    "EldarMurtazin", "Lavale", "Ксюша", "Маруся", "Оксана", "Петя",
    "PetrDidenko", "Петр", "Петрик"
}

stop_words = {
    "то", "ж", "вот", "это", "дело", "гость", "человек", "мальчик", 
    "девушка", "люди", "чувак", "товарищи", "ведущий", "представитель",
    "сегодня", "нельзя", "поддержать", "плохой", "летом", "долгожданный",
    "позапозапрошлое", "который", "всем", "привет", "спасибо", "ладно",
    "окей", "да", "нет", "ну", "ой", "вот", "так", "вот", "там"
}

def is_valid_name(text):
    """Check if text looks like a Russian name"""
    if len(text) < 2:
        return False
    if text in known_hosts or text.lower() in stop_words:
        return False
    # Should not be all caps (usually acronyms)
    if text.isupper() and len(text) > 3:
        return False
    # Should have at least one lowercase letter
    if text and text[0].isupper() and any(c.islower() for c in text):
        return True
    return False

def extract_name_from_context(context, first_lines):
    """Extract guest name from context and first lines"""
    
    context_text = ' '.join(context)
    first_text = ' '.join(first_lines)
    
    # Pattern 1: "Меня зовут [Name]" or "Зовут меня [Name]" in first lines - BEST
    match = re.search(r'(?:Меня|меня) зовут\s+([А-Яа-яЁё]+)', first_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "high", "self_introduction_first_line"
    
    # Pattern 2: "зовут меня [Name]" in first lines
    match = re.search(r'[Зз]вать меня\s+([А-Яа-яЁё]+)', first_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "high", "zvat_introduction"
    
    # Pattern 3: "я [Name]" in first lines (self-identification)
    match = re.search(r'\W я\s+([А-Яа-яЁё]+)(?:\s|,|\.)', first_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "medium", "self_id_first_line"
    
    # Pattern 4: Direct greeting with name in context
    match = re.search(r'здравствуй(?:те)?,?\s+([А-Яа-яЁё]+)', context_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "high", "direct_greeting"
    
    # Pattern 5: "это я про тебя, [Name]" or similar
    match = re.search(r'это я про\s+(?:тебя,?)?\s*([А-Яа-яЁё]+)', context_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "high", "explicit_about_you"
    
    # Pattern 6: "Это я про тебя, Артем" - direct reference
    match = re.search(r'это я про тебя[,.]?\s+([А-Яа-яЁё]+)', context_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "high", "its_about_you"
    
    # Pattern 7: "у нас гость ... [Name]" but avoid "гость" itself
    # Look for name after "гость" in nearby text
    match = re.search(r'(?:гость|ведущий|человек|парень|мальчик)\s+([А-Яа-яЁё]+)(?:\s|,|\.)', context_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "medium", "guest_title"
    
    # Pattern 8: "Ты кто ... [Name]?" or "кого ты, [Name], привел?"
    match = re.search(r'(?:Ты кто|кого ты)[,?]?\s+([А-Яа-яЁё]+)', context_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "medium", "who_are_you"
    
    # Pattern 9: "[Name], ты был раньше" or similar direct address
    match = re.search(r'([А-Яа-яЁё]+),\s+ты\s+(?:был|приходил|пришел)', context_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "high", "direct_address"
    
    # Pattern 10: "[Name], ты был как-то" - another direct addressing
    match = re.search(r'([А-Яа-яЁё]+),\s+ты', context_text)
    if match:
        candidate = match.group(1)
        if is_valid_name(candidate):
            return candidate, "medium", "direct_address_simple"
    
    return None, "none", ""

for item in batches:
    episode = item['episode']
    guest_id = item['guest_id']
    context = item['context']
    first_lines = item['first_lines']
    
    name, confidence, source = extract_name_from_context(context, first_lines)
    
    results.append({
        "episode": episode,
        "guest_id": guest_id,
        "name": name if name else "",
        "confidence": confidence,
        "source": source
    })

# Save results
with open('/Users/ufian/projects/experiment/haiku_batch_30-39.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Обработано гостей: {len(results)}")
high_conf = len([r for r in results if r['confidence'] == 'high'])
medium_conf = len([r for r in results if r['confidence'] == 'medium'])
low_conf = len([r for r in results if r['confidence'] == 'low'])
none_conf = len([r for r in results if r['confidence'] == 'none'])
print(f"Найдено имен (high): {high_conf}")
print(f"Найдено имен (medium): {medium_conf}")
print(f"Найдено имен (low): {low_conf}")
print(f"Не найдено (none): {none_conf}")
print(f"Найдено имен всего: {high_conf + medium_conf + low_conf}")
