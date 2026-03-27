from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator

# Ensure deterministic language detection
DetectorFactory.seed = 0

def detect_lang(text: str) -> str:
    """
    Detects the 2-letter ISO language code of the text.
    Fallback to 'en' if detection fails.
    """
    if not text or len(text.strip()) < 3:
        return 'en'
    try:
        return detect(text)
    except Exception as e:
        print(f"[Translator] Langdetect failed: {e}")
        return 'en'

def translate_to_en(text: str, source_lang: str) -> str:
    """Translates text from source_lang to English."""
    if source_lang == 'en':
        return text
    try:
        translated = GoogleTranslator(source=source_lang, target='en').translate(text)
        return translated if translated else text
    except Exception as e:
        print(f"[Translator] Translation to EN failed: {e}")
        return text

def translate_from_en(text: str, target_lang: str) -> str:
    """Translates English text to target_lang."""
    if target_lang == 'en':
        return text
    try:
        translated = GoogleTranslator(source='en', target=target_lang).translate(text)
        return translated if translated else text
    except Exception as e:
        print(f"[Translator] Translation from EN to {target_lang} failed: {e}")
        return text

# Dictionary of translated verdict badges. The models keep "TRUE", "FALSE", etc., 
# while the localized response sends back translated labels if needed.
# (But it's better to just translate the verdict string using deep-translator too!)
def translate_verdict(verdict: str, target_lang: str) -> str:
    if target_lang == 'en':
        return verdict
    try:
        v_translated = GoogleTranslator(source='en', target=target_lang).translate(verdict.title())
        return v_translated.upper() if v_translated else verdict
    except:
        return verdict
