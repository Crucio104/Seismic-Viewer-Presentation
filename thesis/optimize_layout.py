import glob
import re

def optimize_files():
    files = sorted(glob.glob('chapters/*.tex') + glob.glob('backmatter/*.tex'))
    total_replacements = 0
    
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        orig = content
        
        # Replace float placements
        content = re.sub(r'\\begin\{(figure|table)\}\[H\]', r'\\begin{\1}[htbp]', content)
        
        # Scale figure widths
        content = re.sub(r'width=0\.9[205]?\\textwidth', 'width=0.6\\textwidth', content)
        content = re.sub(r'width=0\.8[05]?\\textwidth', 'width=0.58\\textwidth', content)
        content = re.sub(r'width=0\.7[05]?\\textwidth', 'width=0.55\\textwidth', content)
        
        if content != orig:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content)
            total_replacements += 1
            print(f"Updated: {fpath}")
            
    print(f"Total files updated: {total_replacements}")

if __name__ == '__main__':
    optimize_files()
