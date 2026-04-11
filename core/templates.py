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

def generate_html(fig, is_animated=False, back_button=True, earthquake_data=None):
    """Convert a Plotly figure to a full HTML string with custom overlays."""
    html_content = fig.to_html(
        full_html=True,
        include_plotlyjs='cdn',
        config={'scrollZoom': True, 'displayModeBar': False}
    )

    import os
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    
    extra_scripts = ""

    # Common Styles (Glass Theme)
    common_path = os.path.join(assets_dir, 'viz_common.html')
    with open(common_path, 'r', encoding='utf-8') as f:
        extra_scripts += f.read()

    if is_animated:
        anim_path = os.path.join(assets_dir, 'viz_animated.html')
        with open(anim_path, 'r', encoding='utf-8') as f:
            anim_content = f.read()
        anim_content = anim_content.replace('__ANIMATION_BASE_DURATION_MS__', str(ANIMATION_BASE_DURATION_MS))
        extra_scripts += anim_content

    elif earthquake_data:
        quakes_json = json.dumps(earthquake_data)
        static_path = os.path.join(assets_dir, 'viz_static.html')
        with open(static_path, 'r', encoding='utf-8') as f:
            static_content = f.read()
        static_content = static_content.replace('__QUAKES_JSON__', quakes_json)
        extra_scripts += static_content

    if extra_scripts:
        html_content = html_content.replace('</body>', extra_scripts + '</body>')

    return html_content
