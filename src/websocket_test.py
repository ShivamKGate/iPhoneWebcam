import cv2
import numpy as np
import pyvirtualcam
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import queue
import logging
import os
import base64
import re

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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

logger.info(f"Using template directory: {template_dir}")



# Configure Flask logger
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.DEBUG)

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
                            # Convert frame to RGB (virtual camera expects RGB)
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
    try:
        logger.debug("Rendering index.html template")
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index.html: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/upload', methods=['POST'])
def upload():
    global virtual_camera_thread, running

    if not running:
        return Response("Virtual camera not running", status=400)

    try:
        # Read the image data from the request
        frame_data = request.get_data()
        
        # Convert to numpy array
        nparr = np.frombuffer(frame_data, np.uint8)
        
        # Decode the image
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is not None:
            # Update the frame in the queue
            try:
                # Remove old frame if queue is full
                if frame_queue.full():
                    frame_queue.get_nowait()
                frame_queue.put_nowait(frame)
            except queue.Full:
                pass  # Skip frame if queue is full
            
            return Response("Frame received", status=200)
        else:
            return Response("Invalid frame data", status=400)

    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        return Response("Error processing frame", status=500)

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

@app.route('/health')
def health_check():
    return Response('OK', status=200)

@app.route('/test')
def test():
    """Test endpoint that returns JSON"""
    import platform
    return {
        'status': 'ok',
        'message': 'Server is running',
        'python_version': platform.python_version(),
        'platform': platform.system()
    }

def get_local_ips():
    import socket
    import netifaces

    ips = []
    # Get all network interfaces
    try:
        for interface in netifaces.interfaces():
            try:
                # Get IP addresses for this interface
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        # Filter out localhost
                        if not ip.startswith('127.'):
                            ips.append(ip)
            except ValueError:
                continue
    except ImportError:
        # Fallback method if netifaces is not available
        hostname = socket.gethostname()
        try:
            ips.append(socket.gethostbyname(hostname))
        except socket.gaierror:
            pass
        
    return ips

def test_ports(start_port=8000, end_port=8010):
    """Test a range of ports to find an available one"""
    import socket
    for port in range(start_port, end_port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return None

def main():
    try:
        # Verify templates directory exists
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates')
        if not os.path.exists(template_dir):
            logger.error(f"Templates directory not found at {template_dir}")
            raise FileNotFoundError(f"Templates directory not found at {template_dir}")
            
        # Verify index.html exists
        index_path = os.path.join(template_dir, 'index.html')
        if not os.path.exists(index_path):
            logger.error(f"index.html not found at {index_path}")
            raise FileNotFoundError(f"index.html not found at {index_path}")
            
        logger.info(f"Found template directory at {template_dir}")
        logger.info(f"Found index.html at {index_path}")

        # Start the virtual camera
        start_virtual_camera()
        
        # Find an available port
        port = test_ports()
        if not port:
            logger.error("Could not find an available port")
            raise RuntimeError("No available ports found")
        
        # Get all possible local IPs
        local_ips = get_local_ips()
        
        print("\nServer running!")
        print("\nTry the following URLs on your iPhone:")
        for ip in local_ips:
            print(f"http://{ip}:{port}")
        
        print("\nTroubleshooting steps if URLs don't work:")
        print("1. Make sure your iPhone is on the same WiFi network as this computer")
        print("2. Try connecting to the server from another browser on your computer first")
        print("3. Check your computer's firewall settings")
        print("4. Try accessing the health check endpoint: http://[IP]:{port}/health")
        print("\nTo test network connectivity, try these commands on your iPhone:")
        for ip in local_ips:
            print(f"- Open Safari and try: http://{ip}:{port}/health")
        
        print("\nPress Ctrl+C to stop the server")
        
        # Run the Flask app without debug mode for better performance
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_virtual_camera()

if __name__ == "__main__":
    main()
