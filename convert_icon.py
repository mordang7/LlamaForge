from PIL import Image
import os

def create_ico(source_png, output_ico):
    if not os.path.exists(source_png):
        print(f"Error: {source_png} not found.")
        return

    img = Image.open(source_png)
    
    # Create sizes: 256, 128, 64, 48, 32, 16
    img.save(output_ico, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"Success: Created {output_ico} from {source_png}")

if __name__ == "__main__":
    # Try to find the best source
    if os.path.exists("icon.png") and os.path.getsize("icon.png") > 10000:
        create_ico("icon.png", "LlamaForge.ico")
        create_ico("icon.png", "icons/LlamaForge.ico")
    elif os.path.exists("static/logo.png"):
        create_ico("static/logo.png", "LlamaForge.ico")
        create_ico("static/logo.png", "icons/LlamaForge.ico")
    else:
        print("No suitable high-res icon source found in root or static/logo.png.")
