import base64
import sys

def test():
    try:
        from image_engine import extract_claim_from_image
        print("image_engine imported successfully.")
        
        # Create a small dummy image in base64
        # 1x1 black pixel
        dummy_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        image_bytes = base64.b64decode(dummy_base64)
        
        claim = extract_claim_from_image(image_bytes)
        print("Extracted claim:", claim)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
