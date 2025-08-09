from flask import Flask, request, jsonify
from PIL import Image
import io
import numpy as np
import easyocr
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from flask_cors import CORS
import re

app = Flask(__name__)
load_dotenv()
CORS(app)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(model_name="models/gemini-2.0-flash")

reader = easyocr.Reader(["en"])


@app.route("/extract-text", methods=["POST"])
def extract_text():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image part in the request"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        image_bytes = file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(image)

        # OCR extraction
        ocr_result = reader.readtext(img_np, detail=0)
        extracted_text = "\n".join(ocr_result)
        extracted_text = re.sub(r"[{}]", "", extracted_text)

        # Step 1: Get medicine details in English
        prompt_en = f"""
        You are an expert in reading medicine packaging and prescriptions.
        You will be given text extracted from a medicine image.
        From this text:
        1. Extract the following fields if available:
        - medicine_name
        - dosage
        - usage_instructions
        - frequency
        - expiry_date
        - manufacturer
        - manufacturing_date
        - medicine_use (purpose of the medicine, e.g., "muscle relaxant", "pain relief", "antibiotic")

        2. If 'medicine_use' is NOT found directly in the text, 
        use your own medical knowledge of the medicine name to determine what it is used for 
        and fill it in accurately. 
        Be specific but concise (max 12 words).

        3. Return only a valid JSON array of objects with exactly these keys:
        [
        {{
            "medicine_name": "...",
            "dosage": "...",
            "usage_instructions": "...",
            "frequency": "...",
            "expiry_date": "...",
            "manufacturer": "...",
            "manufacturing_date": "...",
            "medicine_use": "..."
        }}
        ]

        Text from the image:
        {extracted_text}

        If a field is missing and cannot be inferred, return an empty string for it.
        Only output JSON. No explanations.
        """

        response_en = model.generate_content(prompt_en)
        gemini_output_en = response_en.text.strip()
        print(gemini_output_en)
        cleaned_en = re.sub(r"^```json\s*|\s*```$", "", gemini_output_en, flags=re.MULTILINE)
        medicines_en = json.loads(cleaned_en)

        # Step 2: Translate to multiple languages
        languages = {
        "en": "English",
        "hi": "Hindi",
        "bn": "Bengali",
        "ta": "Tamil",
        "gu": "Gujarati"
}

        translations = {}
        for lang_key, lang_name in languages.items():
            prompt_translate = f"""
            Translate the following JSON medicine details into {lang_name}.
            Keep the JSON keys exactly the same but translate the values.
            Only output valid JSON.

            JSON to translate:
            {json.dumps(medicines_en, ensure_ascii=False)}
            """
            resp_lang = model.generate_content(prompt_translate)
            cleaned_lang = re.sub(r"^```json\s*|\s*```$", "", resp_lang.text.strip(), flags=re.MULTILINE)
            translations[lang_key] = json.loads(cleaned_lang)

        return jsonify({
            "extracted_text": extracted_text,
            "medicines": translations
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
