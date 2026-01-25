import json
import re

# Load all batch files
batches = []
for i in range(30, 40):
    with open(f'/Users/ufian/projects/experiment/batch_{i:03d}.json', 'r', encoding='utf-8') as f:
        batches.extend(json.load(f))

results = []

# Known hosts that we should skip
known_hosts = {
    "Umputun", "Bobuk", "Gray", "Ksenks", "Marin_k_a", "Alek.sys", 
    "EldarMurtazin", "Lavale", "Ксюша", "Маруся", "Оксана", "Петя",
    "PetrDidenko", "Петр", "Петрик"
}

def extract_name_from_context(context, first_lines):
    """Extract guest name from context and first lines"""
    
    context_text = ' '.join(context)
    first_text = ' '.join(first_lines)
    full_text = context_text + ' ' + first_text
    
    name = None
    confidence = "none"
    source = ""
    
    # Pattern 1: Direct greeting with name
    # "здравствуй, [Name]" - look for names after greeting
    match = re.search(r'здравствуй(?:те)?,?\s+([А-Яа-яЁё]+)(?:\s|,|\.|!|:|$)', context_text)
    if match:
        candidate = match.group(1)
        if len(candidate) > 2 and candidate not in known_hosts:
            return candidate, "high", "direct_greeting"
    
    # Pattern 2: Introduction in context before first lines
    # "это я про тебя, [Name]" or "Дмитрий" (when mentioned as guest)
    match = re.search(r'это я про тебя,?\s*([А-Яа-яЁё]+)', context_text)
    if match:
        candidate = match.group(1)
        if len(candidate) > 2 and candidate not in known_hosts:
            return candidate, "high", "explicit_mention"
    
    # Pattern 3: "пришел ... [Name]" or "[Name] пришел"
    # Look for names being introduced as guests coming in
    match = re.search(r'(?:пришел|пришла|приходил|приходила|пришёл)\s+(?:к нам\s+)?([А-Яа-яЁё]+)', context_text)
    if match:
        candidate = match.group(1)
        if len(candidate) > 2 and candidate not in known_hosts and candidate not in ["гость", "человек"]:
            return candidate, "medium", "guest_arrival"
    
    # Pattern 4: Self-introduction in first lines
    # "Меня зовут [Name]" or "Зовут меня [Name]"
    match = re.search(r'(?:Меня|меня) зовут\s+([А-Яа-яЁё]+)', first_text)
    if match:
        candidate = match.group(1)
        if len(candidate) > 2 and candidate not in known_hosts:
            return candidate, "high", "self_introduction_first_line"
    
    # Pattern 5: "зовут меня [Name]"
    match = re.search(r'зовут меня\s+([А-Яа-яЁё]+)', first_text)
    if match:
        candidate = match.group(1)
        if len(candidate) > 2 and candidate not in known_hosts:
            return candidate, "high", "self_introduction_zovut"
    
    # Pattern 6: Name mentioned as work company affiliation
    # "Звать меня [Name], я работаю в"
    match = re.search(r'[Зз]вать меня\s+([А-Яа-яЁё]+)', first_text)
    if match:
        candidate = match.group(1)
        if len(candidate) > 2 and candidate not in known_hosts:
            return candidate, "high", "zvat_introduction"
    
    # Pattern 7: In context - "пришел к нам гость [Name]"
    match = re.search(r'(?:гость|ведущий|представитель)\s+([А-Яа-яЁё]+)', context_text)
    if match:
        candidate = match.group(1)
        if len(candidate) > 3 and candidate not in known_hosts:
            return candidate, "medium", "guest_title"
    
    # Pattern 8: Work affiliation intro
    # "я работаю в [Company]" followed by name
    match = re.search(r'я работаю в\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*)', first_text)
    if match:
        company = match.group(1)
        if len(company) > 2 and company not in known_hosts:
            return company, "low", "company_name"
    
    # Pattern 9: "это [Name]"
    match = re.search(r'это\s+([А-Яа-яЁё]+)(?:\s|,|\.)', context_text)
    if match:
        candidate = match.group(1)
        if len(candidate) > 2 and candidate not in known_hosts and candidate not in ["то", "ж", "вот", "дело"]:
            return candidate, "low", "pronoun_introduction"
    
    # Pattern 10: Direct name mention with capitalization in context
    # Look for capitalized Russian names (usually proper nouns)
    matches = re.findall(r'(?:^|\s)([А-ЯЁ][а-яё]+)(?:\s|,|:|$)', context_text)
    if matches:
        for candidate in matches:
            if len(candidate) > 3 and candidate not in known_hosts and candidate not in ["Но", "При", "По", "Все", "Вот", "Это", "Такой"]:
                return candidate, "low", "capitalized_name"
    
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
print(f"Найдено имен (high): {len([r for r in results if r['confidence'] == 'high'])}")
print(f"Найдено имен (medium): {len([r for r in results if r['confidence'] == 'medium'])}")
print(f"Найдено имен (low): {len([r for r in results if r['confidence'] == 'low'])}")
print(f"Найдено имен всего: {len([r for r in results if r['confidence'] != 'none'])}")
