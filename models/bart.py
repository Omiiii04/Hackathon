from transformers import AutoTokenizer, AutoModelForSequenceClassification
import os

MODEL_NAME = "facebook/bart-large-mnli"
SAVE_DIR = "/model" #path to save the model

os.makedirs(SAVE_DIR, exist_ok=True)

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

tokenizer.save_pretrained(SAVE_DIR)
model.save_pretrained(SAVE_DIR)

print(f"Model saved to {SAVE_DIR}")