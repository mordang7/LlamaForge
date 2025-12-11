from PIL import Image, ImageDraw, ImageFont
import os

# Create a simple 64x64 icon
img = Image.new('RGBA', (64, 64), (0, 123, 255, 255))  # Blue background
draw = ImageDraw.Draw(img)

# Draw a llama-like shape (simple rectangle with text)
draw.rectangle([10, 10, 54, 54], fill=(255, 255, 255, 255))
draw.text((20, 25), "LLM", fill=(0, 0, 0, 255))

img.save('icon.png')
print("Icon created: icon.png")
