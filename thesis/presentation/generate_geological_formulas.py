import os
import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams['mathtext.fontset'] = 'cm'
matplotlib.rcParams['font.family'] = 'STIXGeneral'

out_dir = r"c:\Users\aless\Documents\Antigravity Projects\Seismic_Viewer_presentation_version\Seismic-Viewer\thesis\presentation\formulas"
os.makedirs(out_dir, exist_ok=True)

colors = {
    'charcoal': '#1C1819',      # Dark charcoal for light backgrounds
    'bordeaux': '#822433',      # Sapienza Bordeaux
    'white': '#FFFFFF',         # Pure white for dark cards
    'navy': '#204060'           # Slate Navy
}

# 1. Full vertical stacked block (4 formulas)
def gen_vertical_block():
    text_content = (
        r'$\mathbf{Dip}: \quad \delta = \arccos(n_z) \cdot \frac{180^\circ}{\pi}$' + '\n\n' +
        r'$\mathbf{Dip\ Direction}: \quad \theta_{\mathrm{DD}} = \mathrm{atan2}(n_x, n_y) \ (\mathrm{mod}\ 360^\circ)$' + '\n\n' +
        r'$\mathbf{Strike}: \quad \phi_s = (\theta_{\mathrm{DD}} - 90^\circ) \ (\mathrm{mod}\ 360^\circ)$' + '\n\n' +
        r'$\mathbf{Planarity}: \quad P = \frac{\sigma_2 - \sigma_3}{\sigma_1}$'
    )
    for c_name, c_hex in colors.items():
        fig = plt.figure(figsize=(9, 4.2))
        fig.patch.set_alpha(0.0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.patch.set_alpha(0.0)
        ax.axis('off')
        ax.text(0.5, 0.5, text_content, ha='center', va='center', fontsize=20, color=c_hex, linespacing=1.7)
        fpath = os.path.join(out_dir, f'geological_formulas_vertical_{c_name}.png')
        plt.savefig(fpath, dpi=400, transparent=True, bbox_inches='tight', pad_inches=0.08)
        plt.close(fig)

# 2. Compact 2-column grid block (wide format)
def gen_grid_block():
    left_col = (
        r'$\mathbf{Dip}: \quad \delta = \arccos(n_z) \cdot \frac{180^\circ}{\pi}$' + '\n\n' +
        r'$\mathbf{Dip\ Dir}: \quad \theta_{\mathrm{DD}} = \mathrm{atan2}(n_x, n_y) \ (\mathrm{mod}\ 360^\circ)$'
    )
    right_col = (
        r'$\mathbf{Strike}: \quad \phi_s = (\theta_{\mathrm{DD}} - 90^\circ) \ (\mathrm{mod}\ 360^\circ)$' + '\n\n' +
        r'$\mathbf{Planarity}: \quad P = \frac{\sigma_2 - \sigma_3}{\sigma_1}$'
    )
    for c_name, c_hex in colors.items():
        fig = plt.figure(figsize=(13.5, 2.6))
        fig.patch.set_alpha(0.0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.patch.set_alpha(0.0)
        ax.axis('off')
        ax.text(0.02, 0.5, left_col, ha='left', va='center', fontsize=19, color=c_hex, linespacing=1.6)
        ax.text(0.53, 0.5, right_col, ha='left', va='center', fontsize=19, color=c_hex, linespacing=1.6)
        fpath = os.path.join(out_dir, f'geological_formulas_grid_{c_name}.png')
        plt.savefig(fpath, dpi=400, transparent=True, bbox_inches='tight', pad_inches=0.08)
        plt.close(fig)

# 3. Individual formulas
indiv = [
    ('formula_dip', r'$\mathbf{Dip}: \quad \delta = \arccos(n_z) \cdot \frac{180^\circ}{\pi}$', 22),
    ('formula_dip_direction', r'$\mathbf{Dip\ Direction}: \quad \theta_{\mathrm{DD}} = \mathrm{atan2}(n_x, n_y) \ (\mathrm{mod}\ 360^\circ)$', 22),
    ('formula_strike', r'$\mathbf{Strike}: \quad \phi_s = (\theta_{\mathrm{DD}} - 90^\circ) \ (\mathrm{mod}\ 360^\circ)$', 22),
    ('formula_planarity', r'$\mathbf{Planarity}: \quad P = \frac{\sigma_2 - \sigma_3}{\sigma_1}$', 22),
]

def gen_indiv():
    for name, latex_str, fsize in indiv:
        for c_name, c_hex in colors.items():
            fig = plt.figure(figsize=(8.5, 1.8))
            fig.patch.set_alpha(0.0)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.patch.set_alpha(0.0)
            ax.axis('off')
            ax.text(0.5, 0.5, latex_str, ha='center', va='center', fontsize=fsize, color=c_hex)
            fpath = os.path.join(out_dir, f'{name}_{c_name}.png')
            plt.savefig(fpath, dpi=400, transparent=True, bbox_inches='tight', pad_inches=0.08)
            plt.close(fig)

if __name__ == '__main__':
    gen_vertical_block()
    gen_grid_block()
    gen_indiv()
    print("Generated all geological formula images successfully!")
