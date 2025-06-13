import cv2
import numpy as np
import pyvirtualcam
from flask import Flask, render_template, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import queue
import logging
import os
import base64
import re
import qrcode
from io import BytesIO
import socket
import webbrowser

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Setup Flask and SocketIO
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=template_dir)
app.config['SECRET_KEY'] = 'secret!'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=10, ping_interval=5)

# Global variables
frame_queue = queue.Queue(maxsize=1)
virtual_camera = None
virtual_camera_thread = None
running = False
server_url = None

def generate_qr_code(url):
    """Generate QR code for the given URL"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer

def get_local_ips():
    """Get all local IP addresses"""
    try:
        # Try getting IP by connecting to a public DNS
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        primary_ip = s.getsockname()[0]
        s.close()
        return [primary_ip]
    except:
        # Fallback method
        ips = []
        interfaces = socket.getaddrinfo(host=socket.gethostname(), port=None, family=socket.AF_INET)
        for interface in interfaces:
            ip = interface[4][0]
            if not ip.startswith('127.'):
                ips.append(ip)
        return list(set(ips)) or ['127.0.0.1']

class VirtualCameraThread(threading.Thread):
    def __init__(self, width=1280, height=720):
        super().__init__()
        self.width = width
        self.height = height
        self.running = True

    def run(self):
        global virtual_camera
        try:
            with pyvirtualcam.Camera(width=self.width, height=self.height, fps=30) as cam:
                logger.info(f"Virtual camera created: {cam.device}")
                virtual_camera = cam
                
                while self.running:
                    try:
                        frame = frame_queue.get(timeout=1.0)
                        if frame is not None:
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            cam.send(frame_rgb)
                            cam.sleep_until_next_frame()
                    except queue.Empty:
                        continue
                    except Exception as e:
                        logger.error(f"Error processing frame: {str(e)}")
                        continue

        except Exception as e:
            logger.error(f"Error creating virtual camera: {str(e)}")
        finally:
            virtual_camera = None

    def stop(self):
        self.running = False
        self.join()

@app.route('/')
def index():
    return render_template('index_ws.html')

@app.route('/qr')
def qr_code():
    """Generate and serve QR code for the server URL"""
    if server_url:
        img_buffer = generate_qr_code(server_url)
        return send_file(img_buffer, mimetype='image/png')
    return "Server URL not yet available", 400

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    emit('status', {'message': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('start_camera')
def handle_start_camera(data):
    width = data.get('width', 1280)
    height = data.get('height', 720)
    start_virtual_camera(width, height)
    emit('camera_started', {'status': 'success'})

@socketio.on('stop_camera')
def handle_stop_camera():
    stop_virtual_camera()
    emit('camera_stopped', {'status': 'success'})

@socketio.on('frame')
def handle_frame(data):
    global running
    if not running:
        emit('error', {'message': 'Virtual camera not running'})
        return

    try:
        # Extract the base64 data
        image_data = re.sub('^data:image/.+;base64,', '', data)
        
        # Decode base64 string to bytes
        frame_data = base64.b64decode(image_data)
        
        # Convert to numpy array
        nparr = np.frombuffer(frame_data, np.uint8)
        
        # Decode the image
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is not None:
            try:
                if frame_queue.full():
                    frame_queue.get_nowait()
                frame_queue.put_nowait(frame)
                emit('frame_received', {'status': 'success'})
            except queue.Full:
                emit('frame_dropped', {'status': 'queue full'})
        else:
            emit('error', {'message': 'Invalid frame data'})

    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        emit('error', {'message': f'Error processing frame: {str(e)}'})

def start_virtual_camera(width=1280, height=720):
    global virtual_camera_thread, running
    
    if not running:
        running = True
        virtual_camera_thread = VirtualCameraThread(width=width, height=height)
        virtual_camera_thread.start()
        logger.info("Virtual camera started")

def stop_virtual_camera():
    global virtual_camera_thread, running
    
    if running:
        running = False
        if virtual_camera_thread:
            virtual_camera_thread.stop()
            virtual_camera_thread = None
        logger.info("Virtual camera stopped")

def find_available_port(start_port=8080, max_attempts=2):
    """Try to find an available port"""
    import socket
    
    # First try the environment variable if set
    if 'WEBCAM_SERVER_PORT' in os.environ:
        try:
            return int(os.environ['WEBCAM_SERVER_PORT'])
        except:
            pass
    
    # Then try the specified range
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return port
        except OSError:
            continue
    return None

def main():
    global server_url
    try:
        # Get IP addresses
        local_ips = get_local_ips()
        
        # Find an available port
        port = find_available_port()
        if not port:
            print("Error: Could not find an available port!")
            return

        # Set the server URL (use first non-localhost IP)
        server_url = f"http://{local_ips[0]}:{port}"
        
        print("\n=== iPhone Webcam Server ===")
        print(f"\nServer URL: {server_url}")
        print("\nInstructions:")
        print("1. A QR code will open in your browser")
        print("2. Scan the QR code with your iPhone's camera")
        print("3. Tap the notification to open the link in Safari")
        print("4. Allow camera access when prompted")
        print("\nAlternatively, try these URLs on your iPhone:")
        for ip in local_ips:
            print(f"http://{ip}:{port}")
        
        # Open QR code in default browser
        webbrowser.open(f"{server_url}/qr")
        
        # Run the SocketIO app
        socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_virtual_camera()

if __name__ == "__main__":
    main()
