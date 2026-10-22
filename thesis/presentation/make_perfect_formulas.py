import os
import glob
import matplotlib
import matplotlib.pyplot as plt
from PIL import Image

# Matplotlib mathtext configuration
matplotlib.rcParams['mathtext.fontset'] = 'cm'
matplotlib.rcParams['font.family'] = 'STIXGeneral'

out_dir = r"c:\Users\aless\Documents\Antigravity Projects\Seismic_Viewer_presentation_version\Seismic-Viewer\thesis\presentation\formulas"
os.makedirs(out_dir, exist_ok=True)

# Clean up any temporary or test files
temp_patterns = ['*test*', '*debug*', '*compare*', '*see*', 't[1-6].png', 'standalone*']
for pat in temp_patterns:
    for f in glob.glob(os.path.join(out_dir, pat)):
        try:
            os.remove(f)
            print(f"Removed temp file: {os.path.basename(f)}")
        except Exception as e:
            print(f"Could not remove {f}: {e}")

charcoal = '#1C1819'

# Define formulas with exact LaTeX and balanced font sizes
formulas = [
    {
        'filename': 'formula_dip.png',
        'latex': r'$\delta = \arccos(n_z) \cdot \frac{180^\circ}{\pi}$',
        'fontsize': 28
    },
    {
        'filename': 'formula_dip_direction.png',
        'latex': r'$\theta_{\mathrm{DD}} = \mathrm{atan2}(n_x, n_y) \ (\mathrm{mod}\ 360^\circ)$',
        'fontsize': 28
    },
    {
        'filename': 'formula_strike.png',
        'latex': r'$\phi_s = (\theta_{\mathrm{DD}} - 90^\circ) \ (\mathrm{mod}\ 360^\circ)$',
        'fontsize': 28
    },
    {
        'filename': 'formula_planarity.png',
        'latex': r'$P = \frac{\sigma_2 - \sigma_3}{\sigma_1}$',
        'fontsize': 32
    }
]

for item in formulas:
    fig, ax = plt.subplots(figsize=(6, 1.8))
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
    ax.axis('off')
    
    ax.text(
        0.5, 0.5, item['latex'],
        ha='center', va='center',
        fontsize=item['fontsize'],
        color=charcoal
    )
    
    target_path = os.path.join(out_dir, item['filename'])
    plt.savefig(target_path, dpi=400, transparent=True, bbox_inches='tight', pad_inches=0.05)
    plt.close(fig)
    
    # Auto-crop tightly to the actual non-transparent bounding box with 10px safe margin
    im = Image.open(target_path)
    bbox = im.getbbox()
    if bbox:
        pad = 12
        crop_box = (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(im.size[0], bbox[2] + pad),
            min(im.size[1], bbox[3] + pad)
        )
        im_tight = im.crop(crop_box)
        im_tight.save(target_path)
        print(f"Generated {item['filename']}: tightly cropped to {im_tight.size}")
    else:
        print(f"Warning: {item['filename']} has empty bbox!")

print("All 4 geological formulas generated successfully in Charcoal with tight cropping!")
