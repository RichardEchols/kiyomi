#!/usr/bin/env python3
"""
Quick test for Gemini image generation API
Tests both text-to-image and the connection
"""
import os
import sys
from pathlib import Path

# Load env from master env file
def load_env():
    env_file = Path("/Users/richardecholsai2/Documents/Apps/.env.local")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

load_env()

# Try to get API key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: No GEMINI_API_KEY in environment")
    sys.exit(1)

print(f"Using API key: {GEMINI_API_KEY[:20]}...")

try:
    from google import genai
    from google.genai import types
    print("google-genai package imported successfully")
except ImportError as e:
    print(f"Failed to import google-genai: {e}")
    print("Run: pip install google-genai")
    sys.exit(1)

# Initialize client
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("Client initialized successfully")
except Exception as e:
    print(f"Failed to initialize client: {e}")
    sys.exit(1)

# Test models available
print("\n--- Testing Image Generation Models ---")
models_to_test = [
    "gemini-3-pro-image-preview",  # Latest from AI Studio screenshot
    "gemini-2.5-flash-image",      # Nano Banana (standard)
]

test_prompt = "A cute orange fox sitting on a laptop, digital art style"

for model_name in models_to_test:
    print(f"\nTesting model: {model_name}")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=test_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1"
                )
            )
        )

        # Check response
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    print(f"  SUCCESS - Got image data ({len(part.inline_data.data)} bytes)")
                    # Save test image
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(part.inline_data.data))
                    test_path = Path(__file__).parent / "temp" / f"test_{model_name.replace('/', '_')}.png"
                    test_path.parent.mkdir(exist_ok=True)
                    img.save(test_path)
                    print(f"  Saved to: {test_path}")
                    break
                elif hasattr(part, 'text') and part.text:
                    print(f"  Got text response: {part.text[:100]}...")
        else:
            # Check for blocked/error
            if response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    print(f"  Finish reason: {candidate.finish_reason}")
            print(f"  WARNING - No image in response")

    except Exception as e:
        print(f"  ERROR: {e}")

print("\n--- Test Complete ---")
