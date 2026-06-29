import os
import subprocess
import re
import cv2
import easyocr
import numpy as np
import time
import logging
from dotenv import load_dotenv
from deep_translator import GoogleTranslator
import requests
import json
import openai
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

load_dotenv()

load_dotenv()

# Setup debug logging
logging.basicConfig(
    filename='debug_log.txt', 
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Setup debug logging
logging.basicConfig(
    filename='debug_log.txt', 
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_step(msg):
    print(msg)
    logging.debug(msg)

# Initialize Cerebras Client
client = openai.OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=os.getenv("CEREBRAS_API_KEY")
)

# Initialize OCR reader globally
try:
    log_step("Initializing OCR reader with GPU support...")
    # Set gpu=True to use GeForce RTX card
    reader = easyocr.Reader(['en'], gpu=True) 
    log_step("OCR reader initialized successfully on GPU.")
except Exception as e:
    log_step(f"GPU Initialization Failed: {e}. Defaulting to CPU.")
    try:
        reader = easyocr.Reader(['en'], gpu=False)
        log_step("OCR reader initialized successfully on CPU.")
    except Exception as e2:
        log_step(f"Critical OCR Failure: {e2}")
        reader = None

def refine_text_with_ai(text):
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        log_step("No CEREBRAS_API_KEY found in .env. Skipping AI refinement.")
        return text
    
    try:
        response = client.chat.completions.create(
            model="gemma-4-31b",
            messages=[
                {"role": "system", "content": "You are a text correction expert. The user will provide messy OCR text from a video. Your job is to fix typos and make it grammatically correct English while preserving the original meaning. Output ONLY the corrected text. No explanations."},
                {"role": "user", "content": f"Correct this OCR text: {text}"}
            ],
            temperature=0.1
        )
        refined = response.choices[0].message.content.strip()
        return refined
    except Exception as e:
        log_step(f"Cerebras AI Refinement failed: {e}")
        return text

def format_timestamp(seconds):
    td = seconds
    hrs = int(td // 3600)
    mins = int((td % 3600) // 60)
    secs = int(td % 60)
    msecs = int((td % 1) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{msecs:03}"

def extract_subtitles(video_path, srt_path, progress_callback=None):
    log_step(f"Checking for embedded subtitles in {video_path}...")
    ffmpeg_path = r'C:\ffmpeg\bin\ffmpeg.exe'
    command = f'"{ffmpeg_path}" -i "{video_path}" -map 0:s:0 -f srt "{srt_path}"'
    try:
        subprocess.run(command, check=True, capture_output=True, shell=True)
        log_step("Embedded subtitles found and extracted.")
        if progress_callback:
            progress_callback(30)
        return True
    except subprocess.CalledProcessError:
        log_step("No embedded subtitles found. Switching to OCR mode...")
        return run_ocr_extraction(video_path, srt_path, progress_callback)

def run_ocr_extraction(video_path, srt_path, progress_callback=None):
    log_step("Starting OCR extraction...")
    if reader is None:
        log_step("OCR Reader not initialized. Failing.")
        return False
        
    # Use CAP_FFMPEG to attempt hardware acceleration if available
    cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        log_step("Error: Could not open video file for OCR.")
        return False

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    log_step(f"Video opened. FPS: {fps}, Total Frames: {total_frames}")
    
    sample_rate = int(fps * 2) if fps > 0 else 60
    srt_entries = []
    frame_count = 0
    
    while cap.isOpened():
        # FAST SKIP: Use cap.set(cv2.CAP_PROP_POS_FRAMES) to jump directly to the next sample
        # This is much faster than reading every single frame and ignoring them
        if frame_count > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count)
            
        ret, frame = cap.read()
        if not ret:
            log_step("Reached end of video or read failed.")
            break
        
        timestamp = frame_count / fps if fps > 0 else 0
        log_step(f"Processing frame {frame_count} at {timestamp:.2f}s")
        
        # PRE-PROCESSING FOR OCR ACCURACY
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 1. Contrast Enhancement (CLAHE) to make text stand out from backgrounds
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        grey = clahe.apply(grey)
        
        height, width = grey.shape[:2]
        # 2. Targeted Crop (Bottom 20% is where subtitles usually live)
        crop_img = grey[int(height * 0.8):height, 0:width]
        
        try:
            # 3. Dual-Pass Thresholding: Try both Normal and Inverse
            # Pass A: Binary Inverse (Best for white text on dark bg)
            _, thresh_inv = cv2.threshold(crop_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            # Pass B: Binary Normal (Best for dark text on light bg)
            _, thresh_norm = cv2.threshold(crop_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # DEBUG: Save processed frames to see what OCR sees
            cv2.imwrite(f"debug_frame_{frame_count}_inv.jpg", thresh_inv)
            cv2.imwrite(f"debug_frame_{frame_count}_norm.jpg", thresh_norm)

            res_inv = reader.readtext(thresh_inv)
            res_norm = reader.readtext(thresh_norm)
            
            # Pick the result with more detected text
            results = res_inv if len(res_inv) >= len(res_norm) else res_norm
            text = " ".join([res[1] for res in results])
            
            if text.strip():
                log_step(f"Found text: {text}")
                start_t = format_timestamp(timestamp)
                end_t = format_timestamp(timestamp + 2)
                srt_entries.append(f"{len(srt_entries)+1}\n{start_t} --> {end_t}\n{text}\n\n")
        except Exception as e:
            log_step(f"OCR frame error: {e}")

        if progress_callback:
            progress_callback((frame_count / total_frames) * 60, timestamp)
        
        frame_count += sample_rate
    
    cap.release()
    log_step(f"OCR finished. Total entries found: {len(srt_entries)}")
    if srt_entries:
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write("".join(srt_entries))
        return True
    return False

    
    cap.release()
    log_step(f"OCR finished. Total entries found: {len(srt_entries)}")
    if srt_entries:
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write("".join(srt_entries))
        return True
    return False

def translate_srt(input_srt, output_srt, target_lang='en', progress_callback=None):
    with open(input_srt, 'r', encoding='utf-8') as f:
        content = f.read()
    parts = re.split(r'(\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})', content)
    
    # Collect all text for batching
    text_data = []
    for i in range(1, len(parts), 2):
        timestamp = parts[i]
        text = parts[i+1].strip() if i+1 < len(parts) else ""
        text_data.append({"id": i, "timestamp": timestamp, "text": text})
    
    log_step(f"Batch processing {len(text_data)} lines with Gemma-4...")

    # BATCH AI REFINEMENT AND TRANSLATION (Combined into one call)
    translated_map = {}
    if text_data:
        # Combine all lines into one prompt
        raw_text_block = "\n".join([f"Line {item['id']}: {item['text']}" for item in text_data if item['text']])
        
        if raw_text_block:
            try:
                response = client.chat.completions.create(
                    model="gemma-4-31b",
                    messages=[
                        {"role": "system", "content": f"You are a professional translator. I will give you a list of numbered lines of messy OCR text. First, fix the typos and grammar in English, then translate the corrected text into {target_lang}. Return the result in the EXACT same format: 'Line X: translated text'. Do not add any other text or explanations."},
                        {"role": "user", "content": raw_text_block}
                    ],
                    temperature=0.1
                )
                refined_translated_output = response.choices[0].message.content.strip()
                
                # Parse the returned lines back into the map
                for line in refined_translated_output.split('\n'):
                    if ':' in line:
                        try:
                            idx_part, text_part = line.split(':', 1)
                            idx = int(re.search(r'\d+', idx_part).group())
                            translated_map[idx] = text_part.strip()
                        except:
                            continue
            except Exception as e:
                log_step(f"Gemma-4 Batch Translation failed: {e}")

    # Reconstruct the SRT
    translated_content = []
    for i in range(1, len(parts), 2):
        timestamp = parts[i]
        # Fallback: use the translated text, or if that failed, the original text
        text = translated_map.get(i, parts[i+1].strip() if i+1 < len(parts) else "")
        translated_content.append(f"{timestamp}\n{text}\n\n")
        if progress_callback:
            progress_callback(60 + ( (i/len(parts)) * 30))

    with open(output_srt, 'w', encoding='utf-8') as f:
        f.write("".join(translated_content))

def merge_subtitles(video_path, srt_path, output_video, progress_callback=None):
    # Change output extension to .mkv for maximum compatibility with SRT
    output_video_mkv = os.path.splitext(output_video)[0] + ".mkv"
    log_step(f"Merging subtitles into {output_video_mkv}...")
    ffmpeg_path = r'C:\ffmpeg\bin\ffmpeg.exe'
    
    # -y: overwrite output file
    # -i: input video and srt
    # -c copy: copy video/audio streams without re-encoding
    # -c:s srt: use srt codec for subtitles
    command = f'"{ffmpeg_path}" -y -i "{video_path}" -i "{srt_path}" -c copy -c:s srt -map 0:v -map 0:a -map 1:0 "{output_video_mkv}"'
    
    try:
        subprocess.run(command, check=True, capture_output=True, shell=True)
        log_step(f"Merge successful! Saved as {output_video_mkv}")
        if progress_callback: progress_callback(100)
        return True
    except subprocess.CalledProcessError as e:
        log_step(f"FFmpeg Merge Error: {e.stderr.decode() if e.stderr else str(e)}")
        return False

def main(video_file, target_language='en'):
    start_total = time.time()
    base_name = os.path.splitext(video_file)[0]
    temp_srt, translated_srt, output_video = f"{base_name}_orig.srt", f"{base_name}_trans.srt", f"{base_name}_translated.mp4"
    
    metrics = {}

    # 1. Extraction (OCR)
    start_ocr = time.time()
    success = extract_subtitles(video_file, temp_srt)
    metrics['ocr_time'] = time.time() - start_ocr
    
    if success:
        # 2. Translation & Refinement
        start_trans = time.time()
        translate_srt(temp_srt, translated_srt, target_language)
        metrics['trans_time'] = time.time() - start_trans
        
        # 3. Merging
        start_merge = time.time()
        merge_success = merge_subtitles(video_file, translated_srt, output_video)
        metrics['merge_time'] = time.time() - start_merge
        
        if merge_success:
            print(f"\nSuccess! {output_video}")
    
    total_time = time.time() - start_total
    
    # --- PERFORMANCE REPORT ---
    print("\n" + "="*30)
    print("   PERFORMANCE REPORT")
    print("="*30)
    print(f"OCR Stage:       {metrics.get('ocr_time', 0):.2f}s")
    print(f"AI/Trans Stage:  {metrics.get('trans_time', 0):.2f}s")
    print(f"Merge Stage:     {metrics.get('merge_time', 0):.2f}s")
    print("-" * 30)
    print(f"Total Process:   {total_time:.2f}s")
    print("="*30 + "\n")

    for f in [temp_srt, translated_srt]:
        if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'en')
