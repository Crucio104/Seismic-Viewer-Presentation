import os
import json
import plotly.graph_objects as go
from typing import Any

ANIMATION_BASE_DURATION_MS = 1000

# ─── Template Caching ────────────────────────────────────────────────
# Assets are loaded once at startup to improve visualization generation speed.
TEMPLATE_CACHE: dict[str, str] = {}

def _ensure_templates_loaded() -> None:
    """Load HTML assets from the assets directory if not already cached."""
    if TEMPLATE_CACHE:
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, 'assets')
    
    # Files to cache
    files = {
        'common': 'viz_common.html',
        'animated': 'viz_animated.html',
        'cluster': 'viz_cluster.html',
        'static': 'viz_static.html'
    }
    
    for key, filename in files.items():
        path = os.path.join(assets_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                TEMPLATE_CACHE[key] = f.read()
        except Exception as e:
            print(f"Warning: Failed to load template {filename}: {e}")
            TEMPLATE_CACHE[key] = ""


def generate_html(fig: go.Figure, is_animated: bool = False, is_cluster: bool = False, is_3d: bool = False, back_button: bool = True, earthquake_data: dict[str, Any] | None = None, is_fallback: bool = False) -> str:
    """Convert a Plotly figure to a full HTML string with custom overlays and cached templates."""
    _ensure_templates_loaded()

    html_content = fig.to_html(
        full_html=True,
        include_plotlyjs=False,
        config={'scrollZoom': True, 'displayModeBar': False, 'responsive': True},
        default_width='100%',
        default_height='100%'
    )

    # Standardized Loader Injection
    loader_css = (

        '<script src="/assets/plotly.min.js"></script>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;800&display=swap" rel="stylesheet">'
        '<link rel="stylesheet" href="/assets/style.css">'
    )
    
    html_content = html_content.replace('<html>', '<html lang="en-GB">')
    html_content = html_content.replace('<head>', '<head>\n' + loader_css)
    
    extra_scripts = TEMPLATE_CACHE.get('common', "")

    if is_animated:
        quakes_json = json.dumps(earthquake_data) if earthquake_data else "{}"
        anim_content = TEMPLATE_CACHE.get('animated', "").replace('__QUAKES_JSON__', quakes_json)
        anim_content = anim_content.replace('__ANIMATION_BASE_DURATION_MS__', str(ANIMATION_BASE_DURATION_MS))
        extra_scripts += anim_content

    elif is_cluster:
        quakes_json = json.dumps(earthquake_data) if earthquake_data else "{}"
        cluster_content = TEMPLATE_CACHE.get('cluster', "").replace('__QUAKES_JSON__', quakes_json)
        extra_scripts += cluster_content

    elif earthquake_data:
        quakes_json = json.dumps(earthquake_data)
        static_content = TEMPLATE_CACHE.get('static', "").replace('__QUAKES_JSON__', quakes_json)
        extra_scripts += static_content

    # Contextual loading message
    loader_msg = 'Rendering Visualization...'
    if is_animated:
        loader_msg = 'Rendering Animation...'
    elif is_cluster:
        loader_msg = 'Rendering Cluster Analysis...'
    
    loader_html = (
        f'<div id="init-loader">'
        f'  <div class="loader-ring"></div>'
        f'  <p class="loader-text">{loader_msg}</p>'
        f'</div>'
    )

    if is_fallback:
        extra_scripts += f"<script>window.addEventListener('load', () => {{ showStatusToast('Offline: Map tiles unavailable.'); }});</script>"

    if earthquake_data:
        # Inject is_3d flag for UI logic
        extra_scripts += f"\n<script>window.IS_3D_VIEW = {'true' if is_3d else 'false'};</script>"

    if extra_scripts:
        html_content = html_content.replace('<body>', '<body>\n' + loader_html + '\n' + extra_scripts)

    else:
        html_content = html_content.replace('<body>', '<body>\n' + loader_html)

    return html_content
