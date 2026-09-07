import logging
import plotly.graph_objects as go
from typing import Any
from core.config import BASE_DIR, ANIMATION_BASE_DURATION_MS

logger = logging.getLogger(__name__)

# ─── Template Caching ────────────────────────────────────────────────
# Assets are loaded once at startup to improve visualization generation speed.
TEMPLATE_CACHE: dict[str, str] = {}
_TEMPLATE_MTIMES: dict[str, float] = {}

def _ensure_templates_loaded() -> None:
    """Load HTML assets from the assets directory if not already cached or if modified."""
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
            mtime = path.stat().st_mtime
            if key not in TEMPLATE_CACHE or _TEMPLATE_MTIMES.get(key) != mtime:
                with open(path, 'r', encoding='utf-8') as f:
                    TEMPLATE_CACHE[key] = f.read()
                _TEMPLATE_MTIMES[key] = mtime
        except Exception as e:
            logger.warning(f"Failed to load template {filename}: {e}")
            if key not in TEMPLATE_CACHE:
                TEMPLATE_CACHE[key] = ""


def generate_html(fig: go.Figure, is_animated: bool = False, is_cluster: bool = False, is_3d: bool = False, earthquake_data: dict[str, Any] | None = None, is_fallback: bool = False, data_url: str = "", is_subcluster: bool = False) -> str:
    """Convert a Plotly figure to a full HTML string with custom overlays and cached templates."""
    _ensure_templates_loaded()

    if not is_subcluster and earthquake_data and earthquake_data.get('subcluster_target_indices') is not None:
        is_subcluster = True

    html_content = fig.to_html(
        full_html=True,
        include_plotlyjs=False,
        config={'scrollZoom': True, 'displayModeBar': False, 'responsive': True},
        default_width='100%',
        default_height='100%'
    )

    html_content = _inject_head_assets(html_content, is_subcluster=is_subcluster)
    
    # 1. Prepare Content
    loader_msg = _get_loader_message(is_animated, is_cluster)
    loader_html = _get_loader_html(loader_msg, is_subcluster=is_subcluster)
    
    scripts = TEMPLATE_CACHE.get('common', "")
    scripts += _get_view_scripts(is_animated, is_cluster, earthquake_data, data_url, is_fallback, is_3d)

    # 2. Inject into Body
    body_tag = '<body style="background:#050510;margin:0;padding:0;">'
    html_content = html_content.replace('<html>', '<html lang="en-GB" style="background:#050510;">')
    html_content = html_content.replace('<body>', body_tag)
    
    injection = f"\n{loader_html}\n{scripts}"
    html_content = html_content.replace(body_tag, f"{body_tag}{injection}")

    return html_content

def _inject_head_assets(html: str, is_subcluster: bool = False) -> str:
    """Inject CSS and fonts into the <head>."""
    loader_bg = 'rgba(15, 12, 41, 0.6) !important; backdrop-filter: blur(0.8rem); -webkit-backdrop-filter: blur(0.8rem);' if is_subcluster else '#050510 !important;'
    head_css = (
        '<style>'
        'html,body,.js-plotly-plot,.plotly-graph-div{background:#050510 !important;margin:0;padding:0;overflow:hidden;height:100%;width:100%}'
        f'#init-loader{{background:{loader_bg}}}'
        '</style>'
        '<script src="/assets/plotly.min.js"></script>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;800&display=swap" rel="stylesheet">'
        '<link rel="stylesheet" href="/assets/style.css">'
    )
    return html.replace('<head>', f'<head>\n{head_css}')

def _get_loader_message(is_animated: bool, is_cluster: bool) -> str:
    if is_animated:
        return 'Rendering Animation...'
    if is_cluster:
        return 'Rendering Cluster Analysis...'
    return 'Rendering Visualization...'

def _get_loader_html(msg: str, is_subcluster: bool = False) -> str:
    bg_style = 'background:rgba(15, 12, 41, 0.6);backdrop-filter:blur(0.8rem);-webkit-backdrop-filter:blur(0.8rem);' if is_subcluster else 'background:#050510;'
    return (
        f'<div id="init-loader" style="position:fixed;inset:0;z-index:999999;{bg_style}display:flex;flex-direction:column;align-items:center;justify-content:center;">'
        f'  <div class="loader-ring" style="width:4rem;height:4rem;border:0.188rem solid rgba(255,255,255,0.1);border-top-color:#6366f1;border-radius:50%;animation:spin 1s linear infinite;"></div>'
        f'  <p class="loader-text" style="margin-top:1.5rem;font-size:1rem;font-weight:500;color:#e2e8f0;text-align:center;">{msg}</p>'
        f'</div>'
        f'<style>@keyframes spin{{to{{transform:rotate(360deg)}}}}</style>'
    )

def _get_view_scripts(is_animated: bool, is_cluster: bool, earthquake_data: dict[str, Any] | None, data_url: str, is_fallback: bool, is_3d: bool) -> str:
    scripts = ""
    if is_animated:
        content = TEMPLATE_CACHE.get('animated', "").replace('__DATA_URL__', data_url)
        scripts += content.replace('__ANIMATION_BASE_DURATION_MS__', str(ANIMATION_BASE_DURATION_MS))
    elif is_cluster:
        scripts += TEMPLATE_CACHE.get('cluster', "").replace('__DATA_URL__', data_url)
    elif earthquake_data:
        scripts += TEMPLATE_CACHE.get('static', "").replace('__DATA_URL__', data_url)

    if is_fallback:
        scripts += "<script>window.addEventListener('load', () => { showStatusToast('Offline: Map tiles unavailable.'); });</script>"
    
    if earthquake_data or data_url:
        is_static_3d = is_3d and not is_animated and not is_cluster
        scripts += f"\n<script>window.IS_3D_VIEW = {'true' if is_3d else 'false'}; window.IS_3D_STATIC_VIEW = {'true' if is_static_3d else 'false'}; window.IS_CLUSTER_VIEW = {'true' if is_cluster else 'false'};</script>"
    
    return scripts
