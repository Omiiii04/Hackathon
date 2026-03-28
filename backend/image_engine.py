import io
import base64
import requests
from PIL import Image
import easyocr
import torch

print("[ImageEngine] Loading EasyOCR fallback models...")
reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())

print("[ImageEngine] EasyOCR loaded successfully ✅")
print("[ImageEngine] Priority = LM Studio Vision API -> EasyOCR Fallback")

def extract_claim_from_image(image_bytes: bytes) -> str:
    """
    Extracts a claim from an image by:
    1. Hitting the LM Studio Vision local server (Gemma 3 / Qwen-VL)
    2. Falling back to EasyOCR if the LM Studio server is offline
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        print(f"[ImageEngine] Failed to read image bytes: {e}")
        return ""

    # 1. Primary: Local Vision-Language Model via LM Studio
    print("[ImageEngine] Passing image to LM Studio as highly intelligent primary extractor...")
    
    # Safely compress to JPEG buffer first so the MIME type strictly matches
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    safe_image_bytes = buffer.getvalue()
    base64_image = base64.b64encode(safe_image_bytes).decode('utf-8')
    
    try:
        # Dynamically fetch the loaded model names from LM Studio
        models_resp = requests.get("http://localhost:1234/v1/models", timeout=3)
        models_data = models_resp.json()
        loaded_models = [m["id"] for m in models_data.get("data", [])]
        
        # Sort models so "vision" or "vl" are first, and "deepseek" goes last
        loaded_models.sort(key=lambda m: (
            0 if "vl" in m.lower() or "vision" in m.lower() else
            1 if "gemma" in m.lower() or ("qwen" in m.lower() and "deepseek" not in m.lower()) else
            2
        ))
        
        caption = None
        for target_model in loaded_models:
            print(f"[ImageEngine] LM Studio trying model: {target_model}")
            
            response = requests.post(
                "http://localhost:1234/v1/chat/completions",
                json={
                    "model": target_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Extract all readable text from this image exactly as written. If there is no text, explain the main action or subject of this image in one concise sentence. Do not include introductory phrases."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 100,
                    "temperature": 0.1
                },
                timeout=120
            )
            
            # If successful, parse it!
            if response.status_code == 200:
                data = response.json()
                caption = data["choices"][0]["message"]["content"].strip()
                print(f"[ImageEngine] LM Studio Vision output: {caption}")
                return caption
            
            # If the model errors specifically about not supporting images, try the next
            try:
                err_data = response.json()
                msg = err_data.get("error", {}).get("message", "")
                if "does not support images" in msg or "invalid_request_error" in err_data.get("error", {}).get("type", ""):
                    print(f"[ImageEngine] Model {target_model} rejected image payload, skipping...")
                    continue
            except:
                pass
            
            # For other unexpected HTTP errors, break out to EasyOCR
            response.raise_for_status()
            
    except requests.exceptions.ConnectionError:
        print("[ImageEngine] Warning: LM Studio server is offline at http://localhost:1234. Falling back to EasyOCR.")
    except Exception as e:
        print(f"[ImageEngine] LM Studio requests exhausted or failed: {e}. Falling back to EasyOCR.")

    # 2. Fallback: OCR
    print("[ImageEngine] Executing OCR fallback...")
    import numpy as np
    img_np = np.array(image)
    
    ocr_results = reader.readtext(img_np, detail=0)
    text = " ".join(ocr_results).strip()
    
    if len(text) > 0:
        print(f"[ImageEngine] OCR detected text: {text[:50]}...")
        return text

    return ""
