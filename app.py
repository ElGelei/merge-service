from flask import Flask, request, send_file, abort
import subprocess
import os
import uuid

app = Flask(__name__)

@app.route('/merge', methods=['POST'])
def merge():
    # Ensure both the image and audio files are provided
    if 'audio' not in request.files or 'image' not in request.files:
        return abort(400, description="Both audio and image files are required")
    
    audio_file = request.files['audio']
    image_file = request.files['image']
    
    # Save files to a temporary directory
    temp_dir = '/tmp'
    audio_path = os.path.join(temp_dir, f"audio_{uuid.uuid4()}.mp3")
    image_path = os.path.join(temp_dir, f"image_{uuid.uuid4()}.jpg")
    output_path = os.path.join(temp_dir, f"output_{uuid.uuid4()}.mp4")
    
    audio_file.save(audio_path)
    image_file.save(image_path)
    
    # Construct and run the FFmpeg command
    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-i', image_path,
        '-i', audio_path,
        '-c:v', 'libx264', '-tune', 'stillimage',
        '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        output_path
    ]
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        # Clean up if an error occurs
        os.remove(audio_path)
        os.remove(image_path)
        return abort(500, description=f"FFmpeg error: {e.stderr.decode('utf-8')}")
    
    # Clean up the uploaded files
    os.remove(audio_path)
    os.remove(image_path)
    
    # Return the merged video file
    return send_file(output_path, as_attachment=True, attachment_filename="output.mp4")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
