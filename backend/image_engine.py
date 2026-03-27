import io
from PIL import Image
import easyocr
import torch
from transformers import pipeline

# ─────────────────────────────────────────────
# LOAD VISION MODELS
# ─────────────────────────────────────────────
print("[ImageEngine] Loading EasyOCR models...")
# Initialize EasyOCR reader (downloads model ~20MB if first time)
reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())

print("[ImageEngine] Loading BLIP vision-language model...")
# Initialize BLIP (downloads ~900MB if first time)
try:
    image_to_text = pipeline("image-text-to-text", model="Salesforce/blip-image-captioning-base", device=0 if torch.cuda.is_available() else -1)
    print("[ImageEngine] Vision models loaded successfully ✅")
except Exception as e:
    print(f"[ImageEngine] Warning: BLIP model failed to load. Only OCR will be available. {e}")
    image_to_text = None

def extract_claim_from_image(image_bytes: bytes) -> str:
    """
    Extracts a claim from an image by:
    1. Using EasyOCR to read text (for social media screenshots)
    2. Falling back to BLIP image captioning if no text is found (for photographs)
    """
    try:
        # Load image from bytes
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        print(f"[ImageEngine] Failed to read image bytes: {e}")
        return ""

    # 1. Try OCR first
    # easyocr expects a numpy array or file path, PIL Image works if converted to numpy
    import numpy as np
    img_np = np.array(image)
    
    ocr_results = reader.readtext(img_np, detail=0)
    text = " ".join(ocr_results).strip()
    
    if len(text) > 15:
        # We found meaningful text! Assume it's a screenshot.
        print(f"[ImageEngine] OCR detected text: {text[:50]}...")
        return text

    # 2. Fallback to Vision-Language Model
    if image_to_text:
        print("[ImageEngine] No text found. Falling back to BLIP image-to-text...")
        try:
            results = image_to_text(image)
            caption = results[0]['generated_text']
            print(f"[ImageEngine] BLIP caption: {caption}")
            return caption
        except Exception as e:
            print(f"[ImageEngine] BLIP failed: {e}")
            
    # If all fails
    return text # will be < 15 chars or empty
