import os
import math
from PIL import Image, ImageDraw, ImageFont

# Dizionario delle immagini 3D e dei relativi angoli di rotazione del Nord (in gradi).
# 0 gradi = Nord verso l'alto (ore 12)
# 45 gradi = Nord verso l'alto a destra (ore 1:30)
# 90 gradi = Nord a destra (ore 3)
images = {
    "images/3d_visualization.png": 25,
    "images/3d_visualization_tomography.png": 25,
    "images/3d_visualization_uplift_stations.png": 15,
    "images/animated_visualization.png": 135,
    "images/animated_visualization_cylinder_planes.png": 135,
    "images/clustering_visualization.png": 10,
    "images/animated_clustering_without_planes.png": 180,
    "images/animated_clustering_with_planes.png": 180,
    "images/animated_clustering_planes_cylinder.png": 180,
}

def draw_north_arrow_3d(img_path, angle_deg):
    if not os.path.exists(img_path):
        print(f"File non trovato: {img_path}")
        return
        
    backup_path = img_path.replace(".png", "_backup.png")
    if not os.path.exists(backup_path):
        os.system(f"cp '{img_path}' '{backup_path}'")
    else:
        os.system(f"cp '{backup_path}' '{img_path}'")
        
    img = Image.open(img_path).convert('RGBA')
    scale = max(1.0, img.width / 1920.0)
    size = int(160 * scale)
    padding = int(50 * scale)
    
    # In basso a destra
    x_center = img.width - size // 2 - padding
    y_center = img.height - size // 2 - padding
    
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    angle_rad = math.radians(angle_deg)
    
    # Base 3D (Cilindro Grigio in prospettiva isometrica)
    radius = int(size * 0.45)
    tilt = 0.5  # inclinazione per l'effetto 3D
    thickness = int(12 * scale)
    
    base_color_dark = (100, 100, 100, 240)
    base_color_light = (160, 160, 160, 240)
    
    # Disegna lo spessore del cilindro (dal basso verso l'alto)
    for y_off in range(thickness, 0, -1):
        draw.ellipse((x_center - radius, y_center - int(radius*tilt) + y_off, 
                      x_center + radius, y_center + int(radius*tilt) + y_off), 
                     fill=base_color_dark)
                     
    # Disegna il top del cilindro
    draw.ellipse((x_center - radius, y_center - int(radius*tilt), 
                  x_center + radius, y_center + int(radius*tilt)), 
                 fill=base_color_light, outline=(200, 200, 200, 255), width=int(2*scale))
                 
    # Disegna i punti cardinali base sulla faccia del cilindro
    for tick_angle_deg, label in [(0, "N"), (90, "E"), (180, "S"), (270, "W")]:
        ta = math.radians(tick_angle_deg + angle_deg)
        tx = x_center + (radius - 12*scale) * math.sin(ta)
        ty = y_center - (radius - 12*scale) * math.cos(ta) * tilt
        draw.ellipse((tx-3*scale, ty-3*scale, tx+3*scale, ty+3*scale), fill=(60, 60, 60, 255))
    
    # Freccia 3D (Rossa)
    arrow_len = radius * 0.85
    arrow_width = radius * 0.25
    
    # Punta della freccia rialzata dal piano
    elevation = int(12 * scale)
    tip_x = x_center + arrow_len * math.sin(angle_rad)
    tip_y = y_center - arrow_len * math.cos(angle_rad) * tilt - elevation
    
    center_y_elevated = y_center - elevation
    
    left_x = x_center - arrow_width * math.cos(angle_rad)
    left_y = center_y_elevated - arrow_width * math.sin(angle_rad) * tilt
    
    right_x = x_center + arrow_width * math.cos(angle_rad)
    right_y = center_y_elevated + arrow_width * math.sin(angle_rad) * tilt
    
    # Due metà della freccia per l'effetto spigolo/luce (rosso scuro e rosso chiaro)
    arrow_red_light = (230, 60, 60, 255)
    arrow_red_dark = (170, 40, 40, 255)
    
    # Disegno le due metà
    draw.polygon([(x_center, center_y_elevated), (right_x, right_y), (tip_x, tip_y)], fill=arrow_red_dark)
    draw.polygon([(x_center, center_y_elevated), (left_x, left_y), (tip_x, tip_y)], fill=arrow_red_light)
    
    # Testo "N"
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica-Bold.ttc", int(26*scale))
    except:
        try:
            font = ImageFont.truetype("Arial Bold.ttf", int(26*scale))
        except:
            font = ImageFont.load_default()
        
    text = "N"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    tw = text_bbox[2] - text_bbox[0]
    th = text_bbox[3] - text_bbox[1]
    
    tnx = tip_x + (18 * scale) * math.sin(angle_rad) - tw/2
    tny = tip_y - (18 * scale) * math.cos(angle_rad) * tilt - th/2 - (5 * scale)
    
    # Ombra del testo e testo rosso
    draw.text((tnx+2, tny+2), text, fill=(50, 50, 50, 150), font=font)
    draw.text((tnx, tny), text, fill=(230, 40, 40, 255), font=font)
    
    # Sovrapposizione
    out = Image.alpha_composite(img, overlay)
    out.convert('RGB').save(img_path)
    print(f"Bussola 3D (Nord a {angle_deg}°) aggiunta in {img_path}")

print("Inizio applicazione bussola 3D...")
for path, angle in images.items():
    draw_north_arrow_3d(path, angle)
print("Finito!")
