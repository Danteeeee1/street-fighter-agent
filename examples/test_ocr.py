"""快速测试：RapidOCR 对帧数据条数字的识别效果。"""
import sys
import cv2
from rapidocr_onnxruntime import RapidOCR

engine = RapidOCR()


def ocr_region(img_path, x1, y1, x2, y2, scale=2.0, label=""):
    img = cv2.imread(img_path)
    h, w = img.shape[:2]
    x1 = int(x1 * w) if x1 < 1 else x1
    y1 = int(y1 * h) if y1 < 1 else y1
    x2 = int(x2 * w) if x2 < 1 else x2
    y2 = int(y2 * h) if y2 < 1 else y2
    crop = img[y1:y2, x1:x2]
    if scale != 1.0:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    result, _ = engine(crop)
    print(f"=== {label} (region x{x1}-{x2} y{y1}-{y2}) ===")
    if result:
        for box, text, score in result:
            print(f"  [{score}] {text}")
    else:
        print("  (无识别结果)")
    return result


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else "frames/t_30s.png"
    # 底部帧数据条：P1 行 + P2 行
    ocr_region(img, 0.16, 0.715, 0.84, 0.775, 2.5, "P1 帧数据行")
    ocr_region(img, 0.16, 0.795, 0.84, 0.855, 2.5, "P2 帧数据行")
    # 计时器
    ocr_region(img, 0.44, 0.02, 0.56, 0.12, 3.0, "计时器")
