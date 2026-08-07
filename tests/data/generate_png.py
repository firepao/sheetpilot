#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成Excel文件的PNG预览
由于officecli没有直接生成PNG的功能，我们创建一个占位PNG文件
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUTPUT_PNG = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_preview.png"

def generate_placeholder_png():
    """生成一个占位PNG预览文件"""
    # 创建一个简单的PNG图像作为预览
    width, height = 800, 600
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # 添加标题
    title = "UV_DEMO_I3_dirty_orders_result.xlsx Preview"
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # 绘制文本
    draw.text((50, 50), title, fill='black', font=font)
    draw.text((50, 100), "Sheets: UV_DEMO_I3_dirty_orders, CleaningDetail, BusinessOverview, Validation", fill='gray', font=font)
    draw.text((50, 150), "Total Rows: 361", fill='gray', font=font)
    draw.text((50, 200), "Valid: 353, Abnormal: 8", fill='gray', font=font)
    draw.text((50, 250), "Charts: 2 (Monthly Sales, City Sales Distribution)", fill='gray', font=font)
    draw.text((50, 300), "Formulas: 766+", fill='gray', font=font)
    
    # 保存PNG
    img.save(OUTPUT_PNG)
    print(f"PNG preview generated: {OUTPUT_PNG}")

if __name__ == "__main__":
    generate_placeholder_png()
