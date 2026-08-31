import re

with open('/Users/helloworld/Downloads/thesis/chapters/03_architecture.tex', 'r') as f:
    content = f.read()

# 1. Extract Figure 3.3 (fig:dataflow)
fig_regex = re.compile(r'(\\begin\{figure\}\[htbp\].*?\\label\{fig:dataflow\}.*?\\end\{figure\})', re.DOTALL)
fig_match = fig_regex.search(content)
if fig_match:
    fig_text = fig_match.group(1)
    content = content.replace(fig_text, '')
else:
    print("Could not find Figure 3.3")

# 2. Extract Table 3.1 (tab:rest-api)
tab_regex = re.compile(r'(\\begin\{table\}\[htbp\].*?\\label\{tab:rest-api\}.*?\\end\{table\})', re.DOTALL)
tab_match = tab_regex.search(content)
if tab_match:
    tab_text = tab_match.group(1)
    content = content.replace(tab_text, '')
else:
    print("Could not find Table 3.1")

# 3. Rename Section 3.4 and remove the empty Data Flow section
target_section = "\\section{Data Flow Pipeline \\& Protocols}\n\\label{sec:dataflow}\n\\label{sec:protocols}\n\n\n\n\\subsection{Binary Data Transfer Protocol}"
content = content.replace(target_section, '\\section{Binary Data Transfer Protocol}\n\\label{sec:protocols}')
# Just in case there are missing newlines
target_section2 = "\\section{Data Flow Pipeline \\& Protocols}\n\\label{sec:dataflow}\n\\label{sec:protocols}\n\n\\subsection{Binary Data Transfer Protocol}"
content = content.replace(target_section2, '\\section{Binary Data Transfer Protocol}\n\\label{sec:protocols}')

# 4. Insert Table 3.1 at line 57
target_insert_tab = "\\end{itemize}\n\n\\section{Backend Architecture}"
content = content.replace(target_insert_tab, f"\\end{{itemize}}\n\n{tab_text}\n\n\\section{{Backend Architecture}}")

# 5. Insert Figure 3.3
target_insert_fig = "\\section{Binary Data Transfer Protocol}"
content = content.replace(target_insert_fig, f"{fig_text}\n\n\\section{{Binary Data Transfer Protocol}}")

with open('/Users/helloworld/Downloads/thesis/chapters/03_architecture.tex', 'w') as f:
    f.write(content)

print("Done")
