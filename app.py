import os
import uuid
import subprocess
import logging
from flask import Flask, request, jsonify, abort, send_file
from celery import Celery

# Set up logging to print to stdout with timestamps and levels.
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Configure Celery to use Redis.
# Make sure you have set the environment variable REDIS_URL (e.g., via Render’s dashboard).
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
app.config['CELERY_BROKER_URL'] = redis_url
app.config['CELERY_RESULT_BACKEND'] = redis_url

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

@celery.task(bind=True)
def merge_task(self, audio_filename, image_filename):
    logger.info(f"Starting merge task with audio: {audio_filename} and image: {image_filename}")
    temp_dir = '/tmp'
    output_filename = os.path.join(temp_dir, f"output_{uuid.uuid4()}.mp4")
    
    # FFmpeg command to loop the image and merge with audio.
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
    logger.debug(f"FFmpeg command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info(f"FFmpeg completed successfully. Output file: {output_filename}")
        logger.debug(f"FFmpeg stdout: {result.stdout.decode('utf-8')}")
        logger.debug(f"FFmpeg stderr: {result.stderr.decode('utf-8')}")
        return output_filename
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode('utf-8')
        logger.error(f"FFmpeg failed: {error_message}")
        self.update_state(state='FAILURE', meta={'error': error_message})
        raise e

@app.route('/merge', methods=['POST'])
def merge():
    logger.info("Received /merge request")
    if 'audio' not in request.files or 'image' not in request.files:
        logger.error("Missing audio or image file in the request")
        return abort(400, description="Both audio and image files are required")
    
    audio_file = request.files['audio']
    image_file = request.files['image']
    
    temp_dir = '/tmp'
    audio_path = os.path.join(temp_dir, f"audio_{uuid.uuid4()}.mp3")
    image_path = os.path.join(temp_dir, f"image_{uuid.uuid4()}.jpg")
    
    logger.info(f"Saving audio file to: {audio_path}")
    audio_file.save(audio_path)
    logger.info(f"Saving image file to: {image_path}")
    image_file.save(image_path)
    
    try:
        task = merge_task.delay(audio_path, image_path)
        logger.info(f"Enqueued merge task with ID: {task.id}")
        return jsonify({"job_id": task.id}), 202
    except Exception as ex:
        logger.error(f"Error enqueuing merge task: {str(ex)}")
        return abort(500, description="Error enqueuing merge task")

@app.route('/status/<job_id>', methods=['GET'])
def task_status(job_id):
    logger.info(f"Received status request for job_id: {job_id}")
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
    logger.info(f"Status response: {response}")
    return jsonify(response)

@app.route('/test', methods=['GET'])
def test():
    logger.info("Received /test request")
    return "Service is up!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port)
