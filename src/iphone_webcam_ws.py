import cv2
import numpy as np
import pyvirtualcam
from flask import Flask, render_template, request
from datetime import datetime
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import queue
import logging
import os
import base64
import re
import socket
from datetime import datetime

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
    return render_template('index.html')

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

def get_local_ips():
    """Get all local IP addresses"""
    ips = []
    try:
        # Get all network interfaces
        interfaces = socket.getaddrinfo(host=socket.gethostname(), port=None, family=socket.AF_INET)
        for interface in interfaces:
            ip = interface[4][0]
            if not ip.startswith('127.'):
                ips.append(ip)
    except Exception:
        # Fallback to simple method
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ips.append(s.getsockname()[0])
        except Exception:
            pass
        finally:
            s.close()
    return list(set(ips))  # Remove duplicates

def test_network_connectivity():
    """Test network connectivity and get network info"""
    import subprocess
    import re

    network_info = []
    try:
        # Get WiFi network name (SSID) - Windows specific
        result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            ssid_match = re.search(r'SSID\s*:\s*([^\n]+)', result.stdout)
            if ssid_match:
                network_info.append(f"Connected to WiFi: {ssid_match.group(1).strip()}")
    except Exception as e:
        logger.error(f"Error getting WiFi info: {e}")

    return network_info

@app.route('/test')
def network_test():
    """Simple endpoint to test network connectivity"""
    return {
        'status': 'ok',
        'message': 'Server is reachable',
        'timestamp': str(datetime.now())
    }

@app.before_request
def before_request():
    """Log all requests to help with debugging"""
    logger.debug(f"Request from {request.remote_addr}: {request.method} {request.url}")

def main():
    try:
        # Get all possible local IPs
        local_ips = get_local_ips()
        network_info = test_network_connectivity()
        
        print("\nNetwork Information:")
        for info in network_info:
            print(info)
        
        print("\nWebSocket Server running!")
        print("\nTry these URLs on your iPhone (both devices must be on the same WiFi):")
        for ip in local_ips:
            print(f"http://{ip}:3000")
        
        print("\nTroubleshooting steps if URLs don't work:")
        print("1. Verify both devices are on the same WiFi network:")
        print("   - Check the WiFi name on both devices")
        print("   - Try disconnecting and reconnecting to WiFi")
        print("2. Try these tests on your iPhone:")
        for ip in local_ips:
            print(f"   - Open Safari and go to: http://{ip}:3000/")
        print("3. If Safari shows 'Cannot connect to server':")
        print("   - Enable camera access in Safari settings")
        print("   - Clear Safari cache and website data")
        print("   - Allow local network access when prompted")
        print("\nPress Ctrl+C to stop the server")
        
        # Run the SocketIO app
        # Try port 80 first, fall back to 8080 if 80 is not available
        try:
            socketio.run(app, host='0.0.0.0', port=80, debug=False, allow_unsafe_werkzeug=True)
        except OSError:
            print("\nCould not use port 80 (might need admin privileges)")
            print("Trying port 8080 instead...")
            socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_virtual_camera()

if __name__ == "__main__":
    main()
