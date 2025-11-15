# src/batch_clean_and_convert.py
import re
import json
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any

# === CONFIGURATION ===
BASE_DIR = Path(__file__).parent.parent
INPUT_ROOT = BASE_DIR / "text"
CLEAN_ROOT = BASE_DIR / "cleaned_txt"
JSON_ROOT = BASE_DIR / "json"

CLEAN_ROOT.mkdir(parents=True, exist_ok=True)
JSON_ROOT.mkdir(parents=True, exist_ok=True)

# === MARQUEURS VISUELS ===
MARKER_PATTERNS = {
    'قسم': r'╔═══════ (.+?) ═══════╗',
    'باب':  r'╠────── (.+?) ──────╣',
    'فصل':  r'╟┄┄┄┄┄ (.+?) ┄┄┄┄┄╢',
    'فرع':  r'╙⋅⋅⋅⋅⋅ (.+?) ⋅⋅⋅⋅⋅╜',
    'مادة': r'╾───── (.+?) ─────╼',
}

LEVEL_ORDER = ['قسم', 'باب', 'فصل', 'فرع', 'مادة']
LEVEL_TO_INDEX = {level: i for i, level in enumerate(LEVEL_ORDER)}

def get_level(type_name: str) -> int:
    return LEVEL_TO_INDEX.get(type_name, 999)

def extract_number(title: str) -> int:
    match = re.search(r'(أولى?|ثانية?|ثالثة?|رابعة?|خامسة?|سادسة?|سابعة?|ثامنة?|تاسعة?|عاشرة?|\d+)', title)
    if not match:
        return 999
    num_text = match.group(0)
    word_map = {
        'أول': 1, 'أولى': 1, 'تمهيدي': 0,
        'ثاني': 2, 'ثانية': 2,
        'ثالث': 3, 'ثالثة': 3,
        'رابع': 4, 'رابعة': 4,
        'خامس': 5, 'خامسة': 5,
        'سادس': 6, 'سادسة': 6,
        'سابع': 7, 'سابعة': 7,
        'ثامن': 8, 'ثامنة': 8,
        'تاسع': 9, 'تاسعة': 9,
        'عاشر': 10, 'عاشرة': 10,
    }
    return word_map.get(num_text, int(num_text) if num_text.isdigit() else 999)

# === 1. NETTOYAGE (inchangé) ===
def clean_legal_txt(input_path: Path, output_path: Path):
    if not input_path.exists():
        print(f"IGNORÉ : {input_path}")
        return False

    print(f"Nettoyage : {input_path.relative_to(BASE_DIR)}")
    raw = input_path.read_text(encoding="utf-8", errors="ignore")

    clean = re.sub(r'=== PAGE \d+ ===', '', raw)
    clean = re.sub(r'-\s*\d+\s*-', '', clean)
    clean = re.sub(r'^\s*[-.،]+\s*$\n?', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'^\s*$\n', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'([ا-ي٠-٩])\n([ا-ي])', r'\1 \2', clean)
    clean = re.sub(r'([٠-٩])\n([ا-ي])', r'\1 \2', clean)

    ocr_pattern = re.compile(r'\bا\s+ل([ا-ي])')
    matches = ocr_pattern.findall(clean)
    if matches:
        starts = Counter(matches)
        print(f"   OCR (ا ل) : {dict(starts.most_common(3))}")
        for start in starts:
            clean = re.sub(rf'\bا\s+ل{re.escape(start)}', f'ال{start}', clean)

    ocr_fixes = [
        (r'\bا\s+لقسم\b', 'القسم'), (r'\bا\s+لباب\b', 'الباب'),
        (r'\bا\s+لفصل\b', 'الفصل'), (r'\bا\s+لفرع\b', 'الفرع'),
        (r'\bا\s+لمادة\b', 'المادة'),
    ]
    for pat, rep in ocr_fixes:
        clean = re.sub(pat, rep, clean, flags=re.IGNORECASE)

    double_pattern = re.compile(r'\b(\w*?)([ا-ي])\2{2,}(\w*?)\b')
    double_matches = double_pattern.findall(clean)
    if double_matches:
        fixes = {}
        for prefix, letter, suffix in double_matches:
            word = prefix + letter + suffix
            corrected = prefix + letter + suffix
            if word != corrected and word not in ['الله', 'الرحمن', 'الرحيم']:
                fixes[word] = corrected
        fixes = dict(sorted(fixes.items(), key=lambda x: -len(x[0])))
        print(f"   Doublons : {len(fixes)} corrigés")
        for bad, good in fixes.items():
            clean = clean.replace(bad, good)

    clean = clean.replace('\n', ' ')
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = re.sub(r'^\s+|\s+$', '', clean)

    patterns = [
        ('قسم', r'(القسم\s+(?:ال)?(?:أولى?|ثانية?|ثالثة?|رابعة?|خامسة?|سادسة?|سابعة?|ثامنة?|تاسعة?|عاشرة?|\d+)\s*[^\.؛]*?)(?=\s*(?:الباب|الفصل|المادة|$))'),
        ('باب', r'(الباب\s+(?:ال)?(?:أول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع|عاشر|\d+)\s*[^\.؛]*?)(?=\s*(?:الفصل|الفرع|المادة|$))'),
        ('فصل', r'(الفصل\s+(?:ال)?(?:أول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع|عاشر|\d+)\s*[^\.؛]*?)(?=\s*(?:الفرع|المادة|$))'),
        ('فرع', r'(الفرع\s+(?:ال)?(?:أول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع|عاشر|\d+)\s*[^\.؛]*?)(?=\s*(?:المادة|$))'),
        ('مادة', r'(المادة\s+(?:ال)?(?:أولى|ثانية|ثالثة|رابعة|خامسة|سادسة|سابعة|ثامنة|تاسعة|عاشرة|\d+(?:\s*مكرر(?:\s*\d*)?)?)\s*[^\.؛]*?)(?=\s*(?:المادة|$))'),
    ]
    sections = []
    for sec_type, pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        for match in regex.finditer(clean):
            title = match.group(1).strip()
            sections.append({'type': sec_type, 'title': title, 'start': match.start(), 'end': match.end()})
    sections.sort(key=lambda x: x['start'])

    result = []
    last_end = 0
    markers = {
        'قسم': ('╔═══════', '═══════╗'),
        'باب': ('╠──────', '──────╣'),
        'فصل': ('╟┄┄┄┄┄', '┄┄┄┄┄╢'),
        'فرع': ('╙⋅⋅⋅⋅⋅', '⋅⋅⋅⋅⋅╜'),
        'مادة': ('╾─────', '─────╼'),
    }
    for i, sec in enumerate(sections):
        content = clean[last_end:sec['start']].strip()
        if content:
            result.append(f"محتوى: {content}")
            result.append("")
        left, right = markers[sec['type']]
        result.append(f"{left} {sec['title']} {right}")
        if sec['type'] == 'مادة':
            next_start = sections[i + 1]['start'] if i + 1 < len(sections) else len(clean)
            mada_content = clean[sec['end']:next_start].strip()
            if mada_content:
                result.append(f"نص: {mada_content}")
            result.append("")
        result.append("")
        last_end = sec['end']
    final = clean[last_end:].strip()
    if final:
        result.append(f"محتوى: {final}")

    clean_text = '\n'.join(result).strip()
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
    output_path.write_text(clean_text, encoding="utf-8")
    print(f"Nettoyé : {output_path.relative_to(BASE_DIR)}")
    return True

# === 2. PARSING CORRIGÉ : CAPTURE `محتوى:` ET `نص:` ===
def parse_cleaned_txt(input_path: Path) -> List[Dict[str, Any]]:
    text = input_path.read_text(encoding="utf-8")
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]

    structure = []
    stack = [structure]
    current_section = None  # Dernière section détectée
    i = 0

    while i < len(lines):
        line = lines[i]
        matched = False

        # === DÉTECTER MARQUEUR VISUEL ===
        for level, pattern in MARKER_PATTERNS.items():
            match = re.match(pattern, line)
            if match:
                title = match.group(1).strip()
                num = extract_number(title)

                node = {
                    "type": level,
                    "title": title,
                    "number": num,
                    "marker": line.strip(),
                    "content": "",  # Sera rempli
                    "children": []
                }

                # Ajuster la pile
                while len(stack) > 1 and stack[-1] and get_level(stack[-1][-1]["type"]) >= get_level(level):
                    stack.pop()

                stack[-1].append(node)
                if level != "مادة":
                    stack.append(node["children"])
                current_section = node
                matched = True
                i += 1
                break

        # === CAPTURER `محتوى:` OU `نص:` ===
        if not matched and current_section is not None:
            if line.startswith("محتوى:") or line.startswith("نص:"):
                content_text = line.split(":", 1)[1].strip()
                if current_section["content"]:
                    current_section["content"] += " " + content_text
                else:
                    current_section["content"] = content_text
            i += 1
            continue

        # === LIGNES SUPPLÉMENTAIRES (si pas de `محتوى:`) ===
        if not matched and current_section is not None and current_section["type"] != "مادة":
            if not line.startswith(("╔", "╠", "╟", "╙", "╾")):
                if current_section["content"]:
                    current_section["content"] += " " + line.strip()
                else:
                    current_section["content"] = line.strip()

        i += 1

    return structure

# === 3. NETTOYAGE STRUCTURE ===
def clean_structure(nodes: List[Dict]) -> List[Dict]:
    result = []
    for node in nodes:
        content = node.get("content", "").strip()
        if content or node.get("children"):
            node["content"] = content
            node["children"] = clean_structure(node["children"])
            result.append(node)
    return result

# === 4. CONVERSION JSON ===
def convert_to_json(clean_path: Path, json_path: Path):
    print(f"Conversion JSON : {clean_path.relative_to(BASE_DIR)}")
    text = clean_path.read_text(encoding="utf-8")
    intro = ""
    if '╔═══════' in text:
        intro_part = text.split('╔═══════', 1)[0]
        intro = re.sub(r'^محتوى:\s*', '', intro_part)
        intro = re.sub(r'\s+', ' ', intro).strip()

    structure = clean_structure(parse_cleaned_txt(clean_path))

    law = {
        "title": clean_path.stem.replace("_clean", "").replace("-", " "),
        "type": "قانون تنظيمي",
        "intro": intro,
        "structure": structure,
        "source_path": str(clean_path.relative_to(BASE_DIR))
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(law, f, ensure_ascii=False, indent=2)

    def count(n, t=None): 
        return sum(1 for x in n if (t is None or x["type"] == t)) + sum(count(x.get("children", []), t) for x in n)
    
    m = count(structure, "مادة")
    q = count(structure, "قسم")
    b = count(structure, "باب")
    f = count(structure, "فصل")
    print(f"JSON généré : {json_path.relative_to(BASE_DIR)} | {q} قسم | {b} باب | {f} فصل | {m} مادة")

# === 5. TRAITEMENT RÉCURSIF ===
def process_all_files():
    txt_files = sorted([f for f in INPUT_ROOT.rglob("*.txt") if f.is_file()])
    print(f"{len(txt_files)} fichiers .txt trouvés dans {INPUT_ROOT} (et sous-dossiers)\n")

    for txt_file in txt_files:
        rel_path = txt_file.relative_to(INPUT_ROOT)
        clean_file = CLEAN_ROOT / rel_path.parent / (rel_path.stem + "_clean.txt")
        json_file = JSON_ROOT / rel_path.parent / (rel_path.stem + ".json")

        clean_file.parent.mkdir(parents=True, exist_ok=True)
        json_file.parent.mkdir(parents=True, exist_ok=True)

        print(f"\nTRAITEMENT : {txt_file.relative_to(BASE_DIR)}")
        print("-" * 60)

        if clean_legal_txt(txt_file, clean_file):
            convert_to_json(clean_file, json_file)
        else:
            print(f"ÉCHEC : {txt_file.name}")

    print(f"\nTOUS LES FICHIERS TRAITÉS !")
    print(f"Nettoyés → {CLEAN_ROOT}")
    print(f"JSON → {JSON_ROOT}")

if __name__ == "__main__":
    process_all_files()