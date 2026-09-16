import logging
from typing import Any

import plotly.graph_objects as go

from core.config import ANIMATION_BASE_DURATION_MS, BASE_DIR

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
                with open(path, encoding='utf-8') as f:
                    TEMPLATE_CACHE[key] = f.read()
                _TEMPLATE_MTIMES[key] = mtime
        except OSError as e:
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
    loader_msg = _get_loader_message(is_animated, is_cluster, is_subcluster=is_subcluster)
    loader_html = _get_loader_html(loader_msg, is_subcluster=is_subcluster)
    
    is_static_3d = is_3d and not is_animated and not is_cluster
    config_script = (
        '<script>\n'
        f'window.SEISMIC_CONFIG = {{\n'
        f'  dataUrl: "{data_url}",\n'
        f'  animDuration: {ANIMATION_BASE_DURATION_MS},\n'
        f'  is3D: {"true" if is_3d else "false"},\n'
        f'  is3DStatic: {"true" if is_static_3d else "false"},\n'
        f'  isCluster: {"true" if is_cluster else "false"},\n'
        f'  isFallback: {"true" if is_fallback else "false"}\n'
        f'}};\n'
        f'window.IS_3D_VIEW = {"true" if is_3d else "false"};\n'
        f'window.IS_3D_STATIC_VIEW = {"true" if is_static_3d else "false"};\n'
        f'window.IS_CLUSTER_VIEW = {"true" if is_cluster else "false"};\n'
        '</script>'
    )

    scripts = f"{config_script}\n{TEMPLATE_CACHE.get('common', '')}\n"
    scripts += _get_view_scripts(is_animated, is_cluster, earthquake_data, data_url, is_fallback)

    # 2. Inject into Body
    body_tag = '<body style="background:#050510;margin:0;padding:0;">'
    html_content = html_content.replace('<html>', '<html lang="en-GB" style="background:#050510;">')
    html_content = html_content.replace('<body>', body_tag)
    
    injection = f"\n{loader_html}\n{scripts}"
    html_content = html_content.replace(body_tag, f"{body_tag}{injection}")

    return html_content

def _inject_head_assets(html: str, is_subcluster: bool = False) -> str:
    """Inject CSS and fonts into the <head>."""
    head_css = (
        '<script>'
        '(function(){'
        '  function getParentBridge(){'
        '    try{ if(window.parent && window.parent.pywebview) return window.parent.pywebview; }catch(e){}'
        '    return null;'
        '  }'
        '  if(!window.pywebview){'
        '    try{'
        '      Object.defineProperty(window, "pywebview", {'
        '        get: function(){ return getParentBridge(); },'
        '        set: function(val){ Object.defineProperty(window, "pywebview", { value: val, writable: true, configurable: true }); },'
        '        configurable: true'
        '      });'
        '    }catch(e){ window.pywebview = getParentBridge(); }'
        '  }'
        '  if(window.parent && window.parent.pywebview){'
        '    try{ window.dispatchEvent(new Event("pywebviewready")); }catch(e){}'
        '  }'
        '  if(window.parent && window.parent.SeismicApp){'
        '    try{ document.documentElement.classList.add("in-spa"); }catch(e){}'
        '  }'
        '})();'
        '</script>'
        '<style>'
        'html,body,.js-plotly-plot,.plotly-graph-div{background:#050510 !important;margin:0;padding:0;overflow:hidden;height:100%;width:100%}'
        '#init-loader{background:#050510 !important;}'
        '.in-spa #init-loader{display:none !important;}'
        '</style>'
        '<script src="/assets/plotly.min.js" charset="utf-8"></script>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;800&display=swap" media="print" onload="this.media=\'all\'">'
        '<link rel="stylesheet" href="/assets/theme.css">'
        '<link rel="stylesheet" href="/assets/style.css">'
    )
    return html.replace('<head>', f'<head>\n{head_css}')

def _get_loader_message(is_animated: bool, is_cluster: bool, is_subcluster: bool = False) -> str:
    if is_subcluster:
        return 'Rendering Subcluster Analysis...'
    if is_animated:
        return 'Rendering Animation...'
    if is_cluster:
        return 'Rendering Cluster Analysis...'
    return 'Rendering Visualization...'

def _get_loader_html(msg: str, is_subcluster: bool = False) -> str:
    """Build the init-loader HTML.

    Only critical first-paint properties (position, background, z-index) are inlined
    to guarantee the loader is visible before theme.css finishes loading.
    All visual styles (gradient, glow, animation) come from theme.css classes.
    """
    return (
        '<div id="init-loader" style="position:fixed;inset:0;z-index:999999;background:#050510;display:flex;flex-direction:column;align-items:center;justify-content:center;opacity:1;transition:opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1);pointer-events:auto;">'
        f'  <p class="loader-text">{msg}</p>'
        '  <div class="overlay-progress-bar">'
        '    <div class="overlay-progress-fill overlay-progress-track"></div>'
        '  </div>'
        '</div>'
    )

def _get_view_scripts(is_animated: bool, is_cluster: bool, earthquake_data: dict[str, Any] | None, data_url: str, is_fallback: bool) -> str:
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
    
    return scripts
