import json
import re
from collections import defaultdict

# Load all batch files
batches = []
for i in range(30, 40):
    with open(f'/Users/ufian/projects/experiment/batch_{i:03d}.json', 'r', encoding='utf-8') as f:
        batches.extend(json.load(f))

results = []

for item in batches:
    episode = item['episode']
    guest_id = item['guest_id']
    context = item['context']
    first_lines = item['first_lines']
    
    name = None
    confidence = "none"
    source = ""
    
    # Check if this is a known speaker (hosts)
    known_hosts = {
        "Umputun": "Umputun",
        "Bobuk": "Bobuk", 
        "Gray": "Gray",
        "Ksenks": "Ksenks",
        "Marin_k_a": "Marin_k_a",
        "Alek.sys": "Alek.sys",
        "EldarMurtazin": "Eldar Murtazin"
    }
    
    # Parse context for guest introduction patterns
    context_text = ' '.join(context)
    first_lines_text = ' '.join(first_lines)
    
    # Pattern 1: "здравствуй, [Name]" or "у нас гость [Name]" or "его зовут [Name]"
    patterns_intro = [
        r'здравствуй,?\s+([А-Яа-яЁё]+)',
        r'здравствуйте,?\s+([А-Яа-яЁё]+)',
        r'пришел.*?([А-Яа-яЁё]+)',
        r'привел.*?([А-Яа-яЁё]+)',
        r'у нас гость\s+([А-Яа-яЁё]+)',
        r'его зовут\s+([А-Яа-яЁё]+)',
        r'это я про тебя,\s+([А-Яа-яЁё]+)',
        r'Это я про\s+([А-Яа-яЁё]+)',
        r'Ты кто[,?].*?([А-Яа-яЁё]+)',
        r'представьте.*?([А-Яа-яЁё]+)',
        r'Меня зовут\s+([А-Яа-яЁё]+)',
        r'Зовут меня\s+([А-Яа-яЁё]+)',
        r'я\s+([А-Яа-яЁё]+)',
        r'это\s+([А-Яа-яЁё]+)',
    ]
    
    # Try to find in context
    for pattern in patterns_intro:
        matches = re.findall(pattern, context_text)
        if matches:
            candidate = matches[0]
            if candidate not in known_hosts and len(candidate) > 2:
                name = candidate
                confidence = "high" if "зовут" in context_text.lower() or "представь" in context_text.lower() else "medium"
                source = "context_introduction"
                break
    
    # Pattern 2: Check first lines for self-introduction
    if not name:
        first_line_patterns = [
            r'Меня зовут\s+([А-Яа-яЁё]+)',
            r'Зовут меня\s+([А-Яа-яЁё]+)',
            r'я\s+([А-Яа-яЁё]+)',
            r'это\s+([А-Яа-яЁё]+)',
            r'([А-Яа-яЁё]+),?\s+я',
        ]
        
        for pattern in first_line_patterns:
            matches = re.findall(pattern, first_lines_text)
            if matches:
                candidate = matches[0]
                if candidate not in known_hosts and len(candidate) > 2:
                    name = candidate
                    confidence = "medium"
                    source = "first_line_self_intro"
                    break
    
    # Filter out common non-names (verbs, common words)
    if name:
        stop_words = {"добрый", "день", "всем", "привет", "спасибо", "ладно", "окей", "да", "нет", "ну"}
        if name.lower() in stop_words or len(name) < 2:
            name = None
            confidence = "none"
            source = ""
    
    if not name:
        confidence = "none"
    
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
print(f"Найдено имен: {len([r for r in results if r['name']])}")
