import json
import os

ANIMATION_BASE_DURATION_MS = 1000

# ─── Template Caching ────────────────────────────────────────────────
# Assets are loaded once at startup to improve visualization generation speed.
TEMPLATE_CACHE = {}

def _ensure_templates_loaded():
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


def generate_html(fig, is_animated=False, is_cluster=False, is_3d=False, back_button=True, earthquake_data=None, is_fallback=False):
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
        '<style id="unified-loader-css">'
        '*{box-sizing:border-box;margin:0;padding:0}'
        'html,body{width:100%;height:100%;background:#050510;overflow:hidden}'
        '#init-loader,#overlay{position:fixed;top:0;left:0;width:100%;height:100%;z-index:999999;background:#050510;display:flex;flex-direction:column;align-items:center;justify-content:center;transition:opacity 0.3s ease-out;font-family:\'Outfit\',sans-serif}'

        '.loader-ring{width:64px;height:64px;border:3px solid rgba(255,255,255,0.1);border-radius:50%;border-top-color:#6366f1;animation:spin 1s linear infinite}'
        '@keyframes spin{to{transform:rotate(360deg)}}'
        '.loader-text{margin-top:24px;font-size:16px;font-weight:500;color:#e2e8f0;letter-spacing:0.5px;text-align:center;line-height:1;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}'
        '.js-plotly-plot,.plotly-graph-div{width:100%!important;height:100%!important}'
        '</style>'
        '<script src="/assets/plotly.min.js"></script>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;800&display=swap" rel="stylesheet">'
    )
    
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
