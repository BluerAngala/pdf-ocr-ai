#!/usr/bin/env python3
"""生成 Tauri 应用所需的图标文件"""

import os
from PIL import Image, ImageDraw, ImageFont

def create_icon(size, text="OCR", bg_color=(59, 130, 246), fg_color=(255, 255, 255)):
    """创建一个简单的图标"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 绘制圆角矩形背景
    padding = size // 8
    draw.rounded_rectangle(
        [padding, padding, size - padding, size - padding],
        radius=size // 8,
        fill=bg_color
    )
    
    # 绘制文字
    font_size = size // 3
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    # 获取文字尺寸
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - text_height // 4
    
    draw.text((x, y), text, font=font, fill=fg_color)
    
    return img

def main():
    icons_dir = "apps/desktop/src-tauri/icons"
    os.makedirs(icons_dir, exist_ok=True)
    
    # 生成不同尺寸的 PNG
    sizes = [32, 128]
    for size in sizes:
        img = create_icon(size)
        img.save(f"{icons_dir}/{size}x{size}.png", "PNG")
        print(f"Generated {size}x{size}.png")
    
    # 生成 128x128@2x.png (256x256)
    img = create_icon(256)
    img.save(f"{icons_dir}/128x128@2x.png", "PNG")
    print("Generated 128x128@2x.png")
    
    # 生成 ICO 文件 (包含多种尺寸)
    icon_sizes = [16, 32, 48, 64, 128, 256]
    images = [create_icon(s).convert('RGBA') for s in icon_sizes]
    
    # 保存为 ICO
    images[0].save(
        f"{icons_dir}/icon.ico",
        format='ICO',
        sizes=[(s, s) for s in icon_sizes],
        append_images=images[1:]
    )
    print("Generated icon.ico")
    
    # 生成 ICNS (macOS 图标)
    # 简单处理：保存为 PNG，macOS 构建时会处理
    img = create_icon(512)
    img.save(f"{icons_dir}/icon.icns.png", "PNG")
    print("Generated icon.icns.png (placeholder)")
    
    print("\nAll icons generated successfully!")

if __name__ == "__main__":
    main()
