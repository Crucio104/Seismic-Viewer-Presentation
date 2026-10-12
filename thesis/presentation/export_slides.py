import win32com.client
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
pptx_path = os.path.join(script_dir, "Seismic Viewer - Thesis Defense.pptx")
export_dir = os.path.join(script_dir, "exported_slides")
os.makedirs(export_dir, exist_ok=True)

ppt = win32com.client.Dispatch("PowerPoint.Application")
try:
    pres = ppt.Presentations.Open(pptx_path, WithWindow=False)
    for i, slide in enumerate(pres.Slides, 1):
        out_path = os.path.join(export_dir, f"slide_{i:02d}.png")
        slide.Export(out_path, "PNG", 1920, 1080)
        print(f"Exported Slide {i} to {out_path}")
    pres.Close()
finally:
    ppt.Quit()
print("All slides exported successfully!")
