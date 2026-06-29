# Agent Instructions: Subtitle AI

## Core Architecture
- **Hybrid Pipeline**: `Video` $\rightarrow$ `EasyOCR (GPU)` $\rightarrow$ `Gemma-4-31b (Cerebras API)` $\rightarrow$ `FFmpeg` $\rightarrow$ `MKV`.
- **OCR Strategy**: Uses `cv2.threshold` (Binary Inverse + Otsu) for high-contrast text extraction.
- **AI Layer**: Combines text refinement (cleanup) and translation into a single batch prompt to `gemma-4-31b` via the `openai` client.
- **Performance**: Uses `cap.set(cv2.CAP_PROP_POS_FRAMES)` for fast-seeking and `ThreadPoolExecutor` for parallel API calls.

## Critical Setup & Env
- **FFmpeg**: Must be installed at `C:\ffmpeg\bin\ffmpeg.exe`.
- **Environment**: Uses `.env` for `CEREBRAS_API_KEY`.
- **Dependencies**: Requires `easyocr`, `opencv-python`, `openai`, `python-dotenv`, and `deep-translator` (legacy).

## Developer Commands
- **Run Headless (Testing)**: `python translate_subs.py "path/to/video.mp4" "lang_code"`
- **Run GUI**: `python gui_translator.py`

## Key Constraints & Gotchas
- **Container**: Always output to `.mkv` via FFmpeg; `.mp4` fails with SRT streams (Invalid Argument).
- **GPU**: Ensure `gpu=True` in `easyocr.Reader` to avoid extreme CPU slowness.
- **API**: Uses `https://api.cerebras.ai/v1` base URL.
