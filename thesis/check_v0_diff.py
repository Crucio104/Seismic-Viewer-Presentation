import os
import re

with open("versione0_extracted.txt", "r", encoding="utf-8", errors="replace") as f:
    v0_text = f.read()

# Normalize whitespace
v0_words = v0_text.split()
v0_clean = " ".join(v0_words).lower()

def check_file(rel_path):
    with open(rel_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    print(f"\n=== Checking {rel_path} ===")
    
    in_revised = False
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("%") or line_clean.startswith("\\begin") or line_clean.startswith("\\end") or line_clean.startswith("\\caption") or line_clean.startswith("\\label") or line_clean.startswith("\\chapter") or line_clean.startswith("\\section") or line_clean.startswith("\\subsection"):
            continue
        
        # Check if line has words
        words = re.findall(r'\b[a-zA-Z]{4,}\b', line_clean)
        if len(words) >= 4:
            # Check 4-word phrase in v0
            phrase = " ".join(words[:4]).lower()
            present = phrase in v0_clean
            has_revised = "\\revised" in line or "\\color{red}" in line or "\\textcolor{red}" in line
            if not present and not has_revised:
                print(f"Line {i+1} NOT in v0 and NOT revised: {line_clean[:80]}...")

for root, dirs, files in os.walk("."):
    if ".git" in root or ".gemini" in root: continue
    for file in sorted(files):
        if file.endswith(".tex") and ("chapters" in root or "frontmatter" in root or "backmatter" in root):
            check_file(os.path.join(root, file))
