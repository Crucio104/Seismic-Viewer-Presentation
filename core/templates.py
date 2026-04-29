from pathlib import Path
import json
import logging
import plotly.graph_objects as go
from typing import Any
from core.config import BASE_DIR, ANIMATION_BASE_DURATION_MS

logger = logging.getLogger(__name__)

# ─── Template Caching ────────────────────────────────────────────────
# Assets are loaded once at startup to improve visualization generation speed.
TEMPLATE_CACHE: dict[str, str] = {}

def _ensure_templates_loaded() -> None:
    """Load HTML assets from the assets directory if not already cached."""
    if TEMPLATE_CACHE:
        return

    assets_dir = BASE_DIR / 'assets'
    
    # Files to cache
    files = {
        'common': 'viz_common.html',
        'animated': 'viz_animated.html',
        'cluster': 'viz_cluster.html',
        'static': 'viz_static.html'
    }
    
    for key, filename in files.items():
        path = assets_dir / filename
        try:
            with open(path, 'r', encoding='utf-8') as f:
                TEMPLATE_CACHE[key] = f.read()
        except Exception as e:
            logger.warning(f"Failed to load template {filename}: {e}")
            TEMPLATE_CACHE[key] = ""


def generate_html(fig: go.Figure, is_animated: bool = False, is_cluster: bool = False, is_3d: bool = False, back_button: bool = True, earthquake_data: dict[str, Any] | None = None, is_fallback: bool = False, data_url: str = "") -> str:
    """Convert a Plotly figure to a full HTML string with custom overlays and cached templates.
    
    When data_url is provided, the template uses async fetch() to load data from the
    FastAPI REST endpoint instead of inlining JSON directly in the HTML. This reduces
    HTML file size dramatically and enables GZip-compressed data transfer.
    """
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
        anim_content = TEMPLATE_CACHE.get('animated', "").replace('__DATA_URL__', data_url)
        anim_content = anim_content.replace('__ANIMATION_BASE_DURATION_MS__', str(ANIMATION_BASE_DURATION_MS))
        extra_scripts += anim_content

    elif is_cluster:
        cluster_content = TEMPLATE_CACHE.get('cluster', "").replace('__DATA_URL__', data_url)
        extra_scripts += cluster_content

    elif earthquake_data:
        static_content = TEMPLATE_CACHE.get('static', "").replace('__DATA_URL__', data_url)
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

    if earthquake_data or data_url:
        # Inject is_3d flag for UI logic
        extra_scripts += f"\n<script>window.IS_3D_VIEW = {'true' if is_3d else 'false'};</script>"

    if extra_scripts:
        html_content = html_content.replace('<body>', '<body>\n' + loader_html + '\n' + extra_scripts)

    else:
        html_content = html_content.replace('<body>', '<body>\n' + loader_html)

    return html_content
