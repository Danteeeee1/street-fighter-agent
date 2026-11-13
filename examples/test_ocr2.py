"""改进版 OCR 测试：精确裁剪帧数据条文字区 + 亮色提取预处理。"""
import sys
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

engine = RapidOCR()


def ocr_text_region(img_path, x1, y1, x2, y2, scale=4.0, label="", thr_mode="bright"):
    img = cv2.imread(img_path)
    crop = img[y1:y2, x1:x2]
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    if thr_mode == "bright":
        # 文字是亮色(白/彩色高亮)在深色背景上 -> 取高亮像素
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # 判断文字是亮还是暗
        if np.mean(binary) < 128:
            binary = cv2.bitwise_not(binary)
    elif thr_mode == "red":
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 80, 80), (12, 255, 255)) | \
               cv2.inRange(hsv, (160, 80, 80), (180, 255, 255))
        binary = mask
    else:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 白色文字黑底
    result, _ = engine(binary)
    print(f"=== {label} (x{x1}-{x2} y{y1}-{y2} mode={thr_mode}) ===")
    if result:
        for box, text, score in result:
            print(f"  [{score}] {text}")
    else:
        print("  (无识别结果)")
    return result


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else "frames/t_30s.png"
    # 帧数据条文字区（左端）
    ocr_text_region(img, 340, 770, 640, 840, 4.0, "P1 文字区", "bright")
    ocr_text_region(img, 340, 856, 640, 926, 4.0, "P2 文字区", "bright")
    # 计时器（紫红色数字）
    ocr_text_region(img, 880, 20, 1050, 130, 4.0, "计时器", "red")
