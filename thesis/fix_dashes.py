import os
import re

def fix_file(filepath, replacements):
    with open(filepath, 'r') as f:
        content = f.read()
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"Fixed {filepath}")

# abstract.tex
fix_file('/Users/helloworld/Downloads/thesis/frontmatter/abstract.tex', [
    ('backend---leveraging', 'backend, leveraging'),
    ('processing---with', 'processing, with'),
    ('algorithms---including', 'algorithms, including'),
    ('stability---are', 'stability, are')
])

# 01_introduction.tex
fix_file('/Users/helloworld/Downloads/thesis/chapters/01_introduction.tex', [
    ('outputs---publication-quality', 'outputs, such as publication-quality'),
    ('caldera---one of the most densely monitored and potentially hazardous volcanic systems in the world---required', 'caldera, one of the most densely monitored and potentially hazardous volcanic systems in the world, required'),
    ('machine learning--based', 'machine learning-based'),
    ('backend--frontend', 'backend-frontend')
])

# 03_architecture.tex
fix_file('/Users/helloworld/Downloads/thesis/chapters/03_architecture.tex', [
    ('Python--Chromium', 'Python-Chromium'),
    ('Python--JavaScript', 'Python-JavaScript')
])

# 05_visualization.tex
fix_file('/Users/helloworld/Downloads/thesis/chapters/05_visualization.tex', [
    ('hyperparameters---such', 'hyperparameters, such'),
    ('$K$---via', '$K$, via'),
    (r'(\subref{fig:anim-clustering-noplanes}--\subref{fig:anim-clustering-unified})', r'(\subref{fig:anim-clustering-noplanes} to \subref{fig:anim-clustering-unified})')
])

# 08_conclusions.tex
fix_file('/Users/helloworld/Downloads/thesis/chapters/08_conclusions.tex', [
    ('2005--2024', '2005-2024'),
    (r'60\text{--}120', r'60\text{-}120')
])

# appendix_a.tex
fix_file('/Users/helloworld/Downloads/thesis/backmatter/appendix_a.tex', [
    ('Python--JS', 'Python-JS')
])

# 02_background.tex
fix_file('/Users/helloworld/Downloads/thesis/chapters/02_background.tex', [
    ('datasets---comprising', 'datasets, comprising'),
    ('inversions---constitute', 'inversions, constitute'),
    ('file---a workflow', 'file, a workflow'),
    ('capabilities---interactive', 'capabilities, interactive'),
    ('analysis---within', 'analysis, within'),
    ('shape---a critical', 'shape, a critical')
])

