import json

ANIMATION_BASE_DURATION_MS = 1000

def _make_hover(df_subset):
    """Generate descriptive hover text strings from a DataFrame subset."""
    return [
        f"Date: {t}<br>"
        f"Magnitude: {m}<br>"
        f"Latitude: {la:.4f}<br>"
        f"Longitude: {lo:.4f}<br>"
        f"Depth: {abs(d):.4f} km"
        for t, m, la, lo, d in zip(
            df_subset['time_str'], df_subset['mag'],
            df_subset['lat'], df_subset['lon'], df_subset['dep']
        )
    ]

def generate_html(fig, is_animated=False, is_cluster=False, back_button=True, earthquake_data=None):
    """Convert a Plotly figure to a full HTML string with custom overlays."""
    html_content = fig.to_html(
        full_html=True,
        include_plotlyjs='cdn',
        config={'scrollZoom': True, 'displayModeBar': False, 'responsive': True},
        default_width='100%',
        default_height='100%'
    )

    # Standardized Loader Injection (High Priority)
    loader_css = (
        '<style id="unified-loader-css">'
        '*{box-sizing:border-box;margin:0;padding:0}'
        'html,body{width:100%;height:100%;background:#050510;overflow:hidden}'
        '#init-loader,#overlay{position:fixed;top:0;left:0;width:100%;height:100%;z-index:999999;background:#050510;display:flex;flex-direction:column;align-items:center;justify-content:center;transition:opacity 0.6s ease-out;font-family:\'Outfit\',sans-serif}'
        '.loader-ring{width:64px;height:64px;border:3px solid rgba(255,255,255,0.1);border-radius:50%;border-top-color:#6366f1;animation:spin 1s linear infinite}'
        '@keyframes spin{to{transform:rotate(360deg)}}'
        '.loader-text{margin-top:24px;font-size:16px;font-weight:500;color:#e2e8f0;letter-spacing:0.5px;text-align:center;line-height:1}'
        '.js-plotly-plot,.plotly-graph-div{width:100%!important;height:100%!important}'
        '</style>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;800&display=swap" rel="stylesheet">'
    )
    
    # Inject CSS as high as possible in <head>
    html_content = html_content.replace('<head>', '<head>\n' + loader_css)

    import os
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    
    extra_scripts = ""

    # Common Styles (Glass Theme)
    common_path = os.path.join(assets_dir, 'viz_common.html')
    with open(common_path, 'r', encoding='utf-8') as f:
        extra_scripts += f.read()

    if is_animated:
        quakes_json = json.dumps(earthquake_data) if earthquake_data else "{}"
        anim_path = os.path.join(assets_dir, 'viz_animated.html')
        with open(anim_path, 'r', encoding='utf-8') as f:
            anim_content = f.read()
        anim_content = anim_content.replace('__QUAKES_JSON__', quakes_json)
        anim_content = anim_content.replace('__ANIMATION_BASE_DURATION_MS__', str(ANIMATION_BASE_DURATION_MS))
        extra_scripts += anim_content

    elif is_cluster:
        quakes_json = json.dumps(earthquake_data) if earthquake_data else "{}"
        cluster_path = os.path.join(assets_dir, 'viz_cluster.html')
        with open(cluster_path, 'r', encoding='utf-8') as f:
            cluster_content = f.read()
        cluster_content = cluster_content.replace('__QUAKES_JSON__', quakes_json)
        extra_scripts += cluster_content

    elif earthquake_data:
        quakes_json = json.dumps(earthquake_data)
        static_path = os.path.join(assets_dir, 'viz_static.html')
        with open(static_path, 'r', encoding='utf-8') as f:
            static_content = f.read()
        static_content = static_content.replace('__QUAKES_JSON__', quakes_json)
        extra_scripts += static_content

    # Set contextual loading message
    # Set contextual loading message to match Hub labels exactly
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

    # Inject HTML as the very first thing in <body>
    if extra_scripts:
        # Move extra_scripts injection earlier too, but loader_html MUST be first
        html_content = html_content.replace('<body>', '<body>\n' + loader_html + '\n' + extra_scripts)
    else:
        html_content = html_content.replace('<body>', '<body>\n' + loader_html)

    return html_content

