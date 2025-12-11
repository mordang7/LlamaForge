from PIL import Image
import os

def check_size(path):
    if os.path.exists(path):
        with Image.open(path) as img:
            print(f"{path}: {img.size}")
    else:
        print(f"{path}: Not found")

check_size(r"C:\Users\John\.gemini\antigravity\brain\be901ca5-6761-4535-8837-1397ca67db2c\uploaded_image_0_1765464436697.png")
check_size(r"C:\Users\John\.gemini\antigravity\brain\be901ca5-6761-4535-8837-1397ca67db2c\uploaded_image_1_1765464436697.png")
