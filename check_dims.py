from PIL import Image
import os

def check_size(path):
    if os.path.exists(path):
        with Image.open(path) as img:
            print(f"{path}: {img.size}")
    else:
        print(f"{path}: Not found")

check_size("Showcase.png")
check_size(r"C:\Users\John\.gemini\antigravity\brain\be901ca5-6761-4535-8837-1397ca67db2c\new_ui_showcase_1765460997981.png")
