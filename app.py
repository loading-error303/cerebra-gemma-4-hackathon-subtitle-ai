from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import os
import uuid
from translate_subs import extract_subtitles, translate_srt, merge_subtitles

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/translate', methods=['POST'])
def translate_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    target_lang = request.form.get('language', 'en')
    
    file_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{video_file.filename}")
    video_file.save(input_path)
    
    base_name = os.path.splitext(input_path)[0]
    temp_srt = f"{base_name}_orig.srt"
    translated_srt = f"{base_name}_trans.srt"
    output_video = f"{base_name}_translated.mp4"

    try:
        if not extract_subtitles(input_path, temp_srt):
            return jsonify({'error': 'No subtitles found in video'}), 400
        
        translate_srt(temp_srt, translated_srt, target_lang)
        
        if not merge_subtitles(input_path, translated_srt, output_video):
            return jsonify({'error': 'Failed to merge subtitles'}), 500
        
        return send_file(output_video, as_attachment=True)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Cleanup is tricky with send_file, in a real app we'd use a background task or temp files
        pass

if __name__ == "__main__":
    app.run(debug=True, port=5000)
