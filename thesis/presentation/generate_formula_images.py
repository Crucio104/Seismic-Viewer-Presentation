import os
import matplotlib
import matplotlib.pyplot as plt

# Mathtext configuration
matplotlib.rcParams['mathtext.fontset'] = 'cm'
matplotlib.rcParams['font.family'] = 'STIXGeneral'

out_dir = r"c:\Users\aless\Documents\Antigravity Projects\Seismic_Viewer_presentation_version\Seismic-Viewer\thesis\presentation\formulas"
os.makedirs(out_dir, exist_ok=True)

formulas = [
    # 1. Tomography IDW (Interpolazione 3D)
    {
        'name': 'tomography_idw',
        'latex': r'$V_{\mathrm{IDW}}(\mathbf{x}) = \frac{\sum_{i=1}^{k} w_i \, V_i}{\sum_{i=1}^{k} w_i}, \quad w_i = \frac{1}{d(\mathbf{x}, \mathbf{x}_i)^2}$',
        'fontsize': 22,
        'lines': 1
    },
    # 2. Tomography Gaussian Damping (Smorzamento verso baseline 1.75)
    {
        'name': 'tomography_damping',
        'latex': r'$V_{\mathrm{final}}(\mathbf{x}) = \alpha(\mathbf{x}) \, V_{\mathrm{IDW}}(\mathbf{x}) + (1 - \alpha(\mathbf{x})) \cdot 1.75$' + '\n' +
                 r'$\alpha(\mathbf{x}) = \exp\left( -\left(\frac{d_{\mathrm{min}}}{\sigma}\right)^2 \right), \quad \sigma = 2.0\,\mathrm{km}$',
        'fontsize': 20,
        'lines': 2
    },
    # 3. Tomography Full Combined (Tutto in un blocco per la slide)
    {
        'name': 'tomography_full',
        'latex': r'$V_{\mathrm{IDW}}(\mathbf{x}) = \frac{\sum_{i=1}^{k} w_i \, V_i}{\sum_{i=1}^{k} w_i}, \quad w_i = \frac{1}{d(\mathbf{x}, \mathbf{x}_i)^2}$' + '\n' +
                 r'$V_{\mathrm{final}}(\mathbf{x}) = \alpha(\mathbf{x})\,V_{\mathrm{IDW}}(\mathbf{x}) + (1 - \alpha(\mathbf{x}))\cdot 1.75, \quad \alpha(\mathbf{x}) = e^{-(d_{\mathrm{min}}/\sigma)^2}$',
        'fontsize': 19,
        'lines': 2
    },
    # 4. Uplift IDW (GNSS Ground Deformation con esponente Mogi 2.5)
    {
        'name': 'uplift_idw',
        'latex': r'$U(\mathbf{x}) = \frac{\sum_{i=1}^{m} w_i \, U_i}{\sum_{i=1}^{m} w_i}, \quad w_i = \frac{1}{d(\mathbf{x}, \mathbf{x}_i)^{2.5}}$',
        'fontsize': 22,
        'lines': 1
    },
    # 5. Aspect Ratio Correction (Utile anche per la Slide 6!)
    {
        'name': 'aspect_ratio_correction',
        'latex': r'$\mathrm{ratio}_x = \frac{\Delta\lambda \cdot 111.32 \cdot \cos(\bar{\phi})}{\max(d_{\mathrm{lon}},\, d_{\mathrm{lat}})}, \quad \mathrm{ratio}_y = \frac{\Delta\phi \cdot 111.32}{\max(d_{\mathrm{lon}},\, d_{\mathrm{lat}})}$',
        'fontsize': 20,
        'lines': 1
    }
]

# Color palette matching presentation theme
colors = {
    'charcoal': '#1C1819',      # Scuro classico per card chiare
    'bordeaux': '#822433',      # Sapienza Bordeaux
    'white': '#FFFFFF',         # Bianco puro per card scure
    'navy': '#204060'           # Slate Navy
}

generated = []

for f in formulas:
    for c_name, c_hex in colors.items():
        h = 2.2 if f['lines'] == 1 else 3.5
        fig = plt.figure(figsize=(10, h))
        fig.patch.set_alpha(0.0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.patch.set_alpha(0.0)
        ax.axis('off')
        
        ax.text(
            0.5, 0.5, f['latex'],
            horizontalalignment='center',
            verticalalignment='center',
            fontsize=f['fontsize'],
            color=c_hex,
            linespacing=1.6
        )
        
        filename = f"{f['name']}_{c_name}.png"
        filepath = os.path.join(out_dir, filename)
        plt.savefig(filepath, dpi=400, transparent=True, bbox_inches='tight', pad_inches=0.08)
        plt.close(fig)
        generated.append(filename)

print(f"Generated {len(generated)} transparent PNG images in {out_dir}")
