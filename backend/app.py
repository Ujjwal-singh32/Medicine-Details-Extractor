import os
import json
import re
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai
from flask_cors import CORS
from PIL import Image
import io

app = Flask(__name__)
CORS(app)

# Configure Gemini API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(model_name="models/gemini-2.0-flash")

OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")  # Your OCR.Space API key
OCR_SPACE_URL = "https://api.ocr.space/parse/image"


def compress_image_if_needed(image_bytes, max_size_bytes=1_048_576, max_width=1024, quality=75):
    """
    Compress the image bytes if size exceeds max_size_bytes.
    Resizes width to max_width maintaining aspect ratio.
    Returns compressed image bytes.
    """
    if len(image_bytes) <= max_size_bytes:
        # No compression needed
        return image_bytes

    image = Image.open(io.BytesIO(image_bytes))

    # Resize if width is greater than max_width
    if image.width > max_width:
        ratio = max_width / float(image.width)
        new_height = int(float(image.height) * ratio)
        image = image.resize((max_width, new_height), Image.ANTIALIAS)

    compressed_io = io.BytesIO()
    image.save(compressed_io, format="JPEG", quality=quality)
    compressed_io.seek(0)
    compressed_bytes = compressed_io.read()

    return compressed_bytes


@app.route("/extract-text", methods=["POST"])
def extract_text():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image part in the request"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        image_bytes = file.read()

        # Compress only if greater than 1MB
        image_bytes = compress_image_if_needed(image_bytes)

        # Step 1: Send image to OCR.Space API
        ocr_response = requests.post(
            OCR_SPACE_URL,
            files={"filename": (file.filename, image_bytes)},
            data={"apikey": OCR_SPACE_API_KEY, "language": "eng"},
        )
        if ocr_response.status_code != 200:
            return (
                jsonify({"error": "OCR.Space API error", "details": ocr_response.text}),
                500,
            )

        ocr_result = ocr_response.json()

        if not ocr_result.get("IsErroredOnProcessing") and ocr_result.get("ParsedResults"):
            ocr_text = ocr_result["ParsedResults"][0]["ParsedText"]
        else:
            return jsonify({"error": "OCR failed", "details": ocr_result}), 500

        ocr_text = re.sub(r"[{}]", "", ocr_text)  # clean unwanted braces if any

        # Step 2: Prompt Gemini to extract medicine details from OCR text
        prompt_en = f"""
You are an expert in reading medicine packaging and prescriptions.
You will be given text extracted from a medicine image.
From this text:
1. Extract the following fields if available:
- medicine_name
- dosage
- usage_instructions
- medicine_use (purpose of the medicine)

2. If 'usage_instructions' is NOT found directly in the text,
use your own medical knowledge of the medicine name to generate appropriate usage instructions.

3. If 'medicine_use' is NOT found directly in the text, 
use your own medical knowledge of the medicine name to determine what it is used for 
and fill it in accurately. 
Be specific but concise (max 12 words).

3. Return only a valid JSON array of objects with exactly these keys:
[
{{
    "medicine_name": "...",
    "dosage": "...",
    "usage_instructions": "...",
    "medicine_use": "..."
}}
]

Text from the image:
{ocr_text}

If a field is missing and cannot be inferred, return an empty string for it.
Only output JSON. No explanations.
"""
        response_en = model.generate_content(prompt_en)
        gemini_output_en = response_en.text.strip()

        # Clean JSON code fences if present
        cleaned_en = re.sub(
            r"^```json\s*|\s*```$", "", gemini_output_en, flags=re.MULTILINE
        )
        medicines_en = json.loads(cleaned_en)

        # Step 3: Translate JSON into multiple languages
        languages = {
            "en": "English",
            "hi": "Hindi",
            "bn": "Bengali",
            "ta": "Tamil",
            "gu": "Gujarati",
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
            cleaned_lang = re.sub(
                r"^```json\s*|\s*```$", "", resp_lang.text.strip(), flags=re.MULTILINE
            )
            translations[lang_key] = json.loads(cleaned_lang)

        return jsonify({"extracted_text": ocr_text, "medicines": translations})

    except json.JSONDecodeError as jde:
        return (
            jsonify(
                {
                    "error": "Failed to parse JSON from model response",
                    "details": str(jde),
                }
            ),
            500,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
