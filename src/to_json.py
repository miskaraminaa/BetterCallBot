# src/to_json.py
import re
import json
from pathlib import Path
from typing import List, Dict, Any

# === CONFIGURATION ===
BASE_DIR = Path(__file__).parent.parent
CLEAN_DIR = BASE_DIR / "cleaned_txt"
JSON_DIR = BASE_DIR / "json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

TARGET_CLEAN = "العمالات والأقاليم-1707225933208_clean.txt"
INPUT_PATH = CLEAN_DIR / TARGET_CLEAN
OUTPUT_PATH = JSON_DIR / (TARGET_CLEAN.replace("_clean.txt", ".json"))

# === MARQUEURS VISUELS (ON LES GARDE DANS LE JSON) ===
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

def parse_cleaned_txt(input_path: Path) -> List[Dict[str, Any]]:
    if not input_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {input_path}")

    text = input_path.read_text(encoding="utf-8")
    lines = [line.rstrip() for line in text.splitlines()]  # garder les sauts

    structure = []
    stack = [structure]
    current_mada = None
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
                    "marker": line.strip(),  # ON GARDE LE MARQUEUR VISUEL
                    "content": "" if level != "مادة" else None,
                    "children": []
                }

                # Ajuster la pile
                while len(stack) > 1 and stack[-1] and get_level(stack[-1][-1]["type"]) >= get_level(level):
                    stack.pop()

                stack[-1].append(node)
                if level != "مادة":
                    stack.append(node["children"])
                current_mada = node if level == "مادة" else None
                matched = True
                i += 1
                break

        # === CONTENU DE LA مادة ===
        if not matched and current_mada is not None:
            if line.startswith("نص:"):
                current_mada["content"] = line[4:].strip()
            elif current_mada["content"] is None:
                current_mada["content"] = line.strip()
            i += 1
            continue

        # === LIGNE VIDE ENTRE SECTIONS ===
        if not matched and line.strip() == "":
            i += 1
            continue

        i += 1

    return structure

def clean_structure(nodes: List[Dict]) -> List[Dict]:
    result = []
    for node in nodes:
        if node.get("content", "").strip() != "" or node.get("children"):
            node["children"] = clean_structure(node["children"])
            result.append(node)
    return result

def extract_intro(text: str) -> str:
    first_marker = re.search(r'╔═══════', text)
    if not first_marker:
        return ""
    intro = text[:first_marker.start()].strip()
    intro = re.sub(r'^محتوى:\s*', '', intro)
    intro = re.sub(r'\n+', ' ', intro)
    intro = re.sub(r'\s{2,}', ' ', intro)
    return intro.strip()

def txt_to_json(input_path: Path, output_path: Path):
    print(f"Conversion JSON : {input_path.name}")

    text = input_path.read_text(encoding="utf-8")
    intro_content = extract_intro(text)

    raw_structure = parse_cleaned_txt(input_path)
    final_structure = clean_structure(raw_structure)

    law = {
        "title": "القانون التنظيمي رقم 112.14 المتعلق بالعمالات والأقاليم",
        "type": "قانون تنظيمي",
        "intro": intro_content,
        "structure": final_structure
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(law, f, ensure_ascii=False, indent=2)

    def count_nodes(nodes, target_type=None):
        count = 0
        for node in nodes:
            if target_type is None or node["type"] == target_type:
                count += 1
            count += count_nodes(node.get("children", []), target_type)
        return count

    total_mada = count_nodes(final_structure, "مادة")
    total_qism = count_nodes(final_structure, "قسم")
    total_bab = count_nodes(final_structure, "باب")
    total_fasl = count_nodes(final_structure, "فصل")
    total_fara = count_nodes(final_structure, "فرع")

    print(f"JSON généré : {output_path.name}")
    print(f"→ {total_qism} قسم | {total_bab} باب | {total_fasl} فصل | {total_fara} فرع | {total_mada} مادة")
    print(f"→ Marqueurs visuels : CONSERVÉS dans le JSON")

if __name__ == "__main__":
    try:
        txt_to_json(INPUT_PATH, OUTPUT_PATH)
        print("Conversion terminée avec succès !")
    except Exception as e:
        print(f"ERREUR : {e}")
        import traceback
        traceback.print_exc()