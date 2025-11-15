# src/clean_txt.py
import re
from pathlib import Path
from collections import Counter

# === CONFIGURATION ===
BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / "text" / "القوانين التنظيمية"
CLEAN_DIR = BASE_DIR / "cleaned_txt"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FILE = "العمالات والأقاليم-1707225933208.txt"
INPUT_PATH = INPUT_DIR / TARGET_FILE
OUTPUT_PATH = CLEAN_DIR / (TARGET_FILE.replace(".txt", "_clean.txt"))


def clean_legal_txt(input_path: Path, output_path: Path):
    if not input_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {input_path}")

    print(f"Nettoyage de : {input_path.name}")
    raw = input_path.read_text(encoding="utf-8", errors="ignore")

    # === 1. Nettoyage de base ===
    clean = re.sub(r'=== PAGE \d+ ===', '', raw)
    clean = re.sub(r'-\s*\d+\s*-', '', clean)
    clean = re.sub(r'^\s*[-.،]+\s*$\n?', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'^\s*$\n', '', clean, flags=re.MULTILINE)

    # === 2. Corriger mots cassés (sauts de ligne dans les mots) ===
    clean = re.sub(r'([ا-ي٠-٩])\n([ا-ي])', r'\1 \2', clean)
    clean = re.sub(r'([٠-٩])\n([ا-ي])', r'\1 \2', clean)

    # === 3. Correction OCR : "ا ل" + lettre → "ال" + lettre ===
    ocr_pattern = re.compile(r'\bا\s+ل([ا-ي])')
    matches = ocr_pattern.findall(clean)
    if matches:
        starts = Counter(matches)
        print(f"Corrections OCR (ا ل) : {dict(starts.most_common(5))}")
        for start in starts:
            clean = re.sub(rf'\bا\s+ل{re.escape(start)}', f'ال{start}', clean)

    # === 4. Forcer "ا لقسم" → "القسم", etc. (OCR) ===
    ocr_fixes = [
        (r'\bا\s+لقسم\b', 'القسم'),
        (r'\bا\s+لباب\b',  'الباب'),
        (r'\bا\s+لفصل\b',  'الفصل'),
        (r'\bا\s+لفرع\b',  'الفرع'),
        (r'\bا\s+لمادة\b',  'المادة'),
    ]
    for pat, rep in ocr_fixes:
        clean = re.sub(pat, rep, clean, flags=re.IGNORECASE)

    # === 5. Corriger les lettres doublées (OCR) ===
    double_letter_pattern = re.compile(r'\b(\w*?)([ا-ي])\2{2,}(\w*?)\b')
    double_matches = double_letter_pattern.findall(clean)
    if double_matches:
        fixes = {}
        for prefix, letter, suffix in double_matches:
            word = prefix + letter + suffix
            corrected = prefix + letter + suffix
            if word != corrected and word not in ['الله', 'الرحمن', 'الرحيم']:
                fixes[word] = corrected
        fixes = dict(sorted(fixes.items(), key=lambda x: -len(x[0])))
        print(f"Corrections doublons détectées : {len(fixes)} (ex: {list(fixes.items())[:3]})")
        for bad, good in fixes.items():
            clean = clean.replace(bad, good)

    # === 6. Remplacer tous les sauts de ligne par un espace ===
    clean = clean.replace('\n', ' ')

    # === 7. Normaliser les espaces ===
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = re.sub(r'^\s+|\s+$', '', clean)

    # === 8. DÉTECTION ROBUSTE DES SECTIONS ===
    patterns = [
        ('قسم',   r'(القسم\s+(?:ال)?(?:أولى?|ثانية?|ثالثة?|رابعة?|خامسة?|سادسة?|سابعة?|ثامنة?|تاسعة?|عاشرة?|\d+)\s*[^\.؛]*?)(?=\s*(?:الباب|الفصل|المادة|$))'),
        ('باب',    r'(الباب\s+(?:ال)?(?:أول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع|عاشر|\d+)\s*[^\.؛]*?)(?=\s*(?:الفصل|الفرع|المادة|$))'),
        ('فصل',    r'(الفصل\s+(?:ال)?(?:أول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع|عاشر|\d+)\s*[^\.؛]*?)(?=\s*(?:الفرع|المادة|$))'),
        ('فرع',    r'(الفرع\s+(?:ال)?(?:أول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع|عاشر|\d+)\s*[^\.؛]*?)(?=\s*(?:المادة|$))'),
        ('مادة',   r'(المادة\s+(?:ال)?(?:أولى|ثانية|ثالثة|رابعة|خامسة|سادسة|سابعة|ثامنة|تاسعة|عاشرة|\d+(?:\s*مكرر(?:\s*\d*)?)?)\s*[^\.؛]*?)(?=\s*(?:المادة|$))'),
    ]

    sections = []
    for sec_type, pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        for match in regex.finditer(clean):
            title = match.group(1).strip()
            sections.append({
                'type': sec_type,
                'title': title,
                'start': match.start(),
                'end': match.end()
            })

    sections.sort(key=lambda x: x['start'])

    # === 9. RECONSTRUIRE : LIGNE PAR LIGNE + VISUEL + SÉPARATION ===
    result = []
    last_end = 0

    for i, sec in enumerate(sections):
        # Contenu avant la section
        content = clean[last_end:sec['start']].strip()
        if content:
            result.append(f"محتوى: {content}")
            result.append("")  # ligne vide

        # Marqueur visuel + titre
        markers = {
            'قسم': ('╔═══════', '═══════╗'),
            'باب':  ('╠──────',  '──────╣'),
            'فصل':  ('╟┄┄┄┄┄',  '┄┄┄┄┄╢'),
            'فرع':  ('╙⋅⋅⋅⋅⋅',  '⋅⋅⋅⋅⋅╜'),
            'مادة': ('╾─────',  '─────╼'),
        }
        left, right = markers[sec['type']]
        result.append(f"{left} {sec['title']} {right}")

        # Contenu de la مادة
        if sec['type'] == 'مادة':
            next_start = sections[i + 1]['start'] if i + 1 < len(sections) else len(clean)
            mada_content = clean[sec['end']:next_start].strip()
            if mada_content:
                result.append(f"نص: {mada_content}")
            result.append("")  # ligne vide

        # Séparation entre sections
        result.append("")

        last_end = sec['end']

    # Dernier contenu
    final = clean[last_end:].strip()
    if final:
        result.append(f"محتوى: {final}")

    clean_text = '\n'.join(result).strip()
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)

    # === SAUVEGARDE ===
    output_path.write_text(clean_text, encoding="utf-8")

    # === STATS DÉTAILLÉES ===
    mada_list = [s['title'] for s in sections if s['type'] == 'مادة']
    print(f"\nTOTAL DÉTECTÉ : {len(sections)} sections")
    print(f"   قسم : {sum(1 for s in sections if s['type'] == 'قسم')}")
    print(f"   باب  : {sum(1 for s in sections if s['type'] == 'باب')}")
    print(f"   فصل  : {sum(1 for s in sections if s['type'] == 'فصل')}")
    print(f"   فرع  : {sum(1 for s in sections if s['type'] == 'فرع')}")
    print(f"   مادة : {len(mada_list)}")

    print(f"\nPREMIÈRES MADAS :")
    for m in mada_list[:10]:
        print(f"   └─ {m}")

    print(f"\nDERNIÈRES MADAS :")
    for m in mada_list[-10:]:
        print(f"   └─ {m}")

    print(f"\nFichier nettoyé : {output_path.name}")
    print(f"→ {len([l for l in clean_text.splitlines() if l.strip()])} lignes générées")


if __name__ == "__main__":
    try:
        clean_legal_txt(INPUT_PATH, OUTPUT_PATH)
        print("\nNettoyage terminé avec succès !")
    except Exception as e:
        print(f"ERREUR : {e}")