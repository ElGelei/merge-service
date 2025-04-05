from flask import Flask, request, jsonify, abort
from celery import Celery
import subprocess, os, uuid

app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
app.config['CELERY_RESULT_BACKEND'] = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

@celery.task(bind=True)
def merge_task(self, audio_filename, image_filename):
    temp_dir = '/tmp'
    output_filename = os.path.join(temp_dir, f"output_{uuid.uuid4()}.mp4")
    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-i', image_filename,
        '-i', audio_filename,
        '-c:v', 'libx264', '-tune', 'stillimage',
        '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        output_filename
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_filename
    except subprocess.CalledProcessError as e:
        self.update_state(state='FAILURE', meta={'error': e.stderr.decode('utf-8')})
        raise e

@app.route('/merge', methods=['POST'])
def merge():
    if 'audio' not in request.files or 'image' not in request.files:
        return abort(400, description="Both audio and image files are required")
    
    audio_file = request.files['audio']
    image_file = request.files['image']
    
    temp_dir = '/tmp'
    audio_path = os.path.join(temp_dir, f"audio_{uuid.uuid4()}.mp3")
    image_path = os.path.join(temp_dir, f"image_{uuid.uuid4()}.jpg")
    
    audio_file.save(audio_path)
    image_file.save(image_path)
    
    # Enqueue the merge task
    task = merge_task.delay(audio_path, image_path)
    return jsonify({"job_id": task.id}), 202

@app.route('/status/<job_id>', methods=['GET'])
def task_status(job_id):
    task = merge_task.AsyncResult(job_id)
    if task.state == 'PENDING':
        response = {"state": task.state, "status": "Pending..."}
    elif task.state != 'FAILURE':
        response = {
            "state": task.state,
            "result": task.result if task.state == 'SUCCESS' else None
        }
    else:
        response = {"state": task.state, "status": str(task.info)}
    return jsonify(response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

@app.route('/test', methods=['GET'])
def test():
    return "Service is up!", 200
