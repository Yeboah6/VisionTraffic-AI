from flask import current_app
from datetime import datetime
from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
import re
import cv2
import time
import subprocess
import shutil
import os
from threading import Thread

class Camera(db.Model):
    __tablename__ = 'cameras'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_id = db.Column(db.String(50), unique=True) #CAM_MAIN_001
    name = db.Column(db.String(100), nullable=False, index=True)
    rtsp_url = db.Column(db.String(200), nullable=False)
    camera_type = db.Column(db.String(50), nullable=False)
    manufacturer = db.Column(db.String(50), nullable=False)
    model_number = db.Column(db.String(50), nullable=False)
    resolution = db.Column(db.String(20), nullable=False)
    frame_rate = db.Column(db.String(10), nullable=False)
    ip_address = db.Column(db.String(15), nullable=False)
    stream_protocol = db.Column(db.String(10), default='rtsp')  # e.g., rtsp, http
    port = db.Column(db.Integer, nullable=False)
    stream_path = db.Column(db.String(100), nullable=False) # e.g., /live.sdp
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Should be encrypted in production
    address = db.Column(db.String(50), nullable=False)
    direction = db.Column(db.String(20))
    elevation = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    connection_timeout = db.Column(db.Integer, default=10)  # seconds
    maintenance = db.Column(db.String(50))  # or another appropriate type
    camera_group = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stream_process_pid = db.Column(db.Integer)  # Store process ID for stream conversion
    last_stream_check = db.Column(db.DateTime)  # Track when stream was last checked
    
    # Relationships
    location_id = db.Column(db.UUID(36), db.ForeignKey('locations.id'))
    location = db.relationship('Location', back_populates='cameras')
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator = db.relationship('User', backref='cameras')
    
    signal_id = db.Column(db.UUID(50), db.ForeignKey('signals.id'))
    
    @staticmethod
    def generate_display_id(location_name=None):
        """Auto-generates CAM_LOC_001 format"""
        prefix = "CAM_" + (
            re.sub(r'\W+', '', location_name.split()[0]).upper()[:3] 
            if location_name 
            else "UNK"
        )
        
        last_cam = Camera.query.filter(
            Camera.display_id.like(f"{prefix}_%")
        ).order_by(Camera.display_id.desc()).first()
        
        last_num = int(last_cam.display_id.split('_')[-1]) if last_cam else 0
        return f"{prefix}_{last_num + 1:03d}"
    
    def toggle_status(self):
        self.is_active = not self.is_active
        db.session.commit()
        return self.is_active
    
    def test_rtsp_connection(self):
        """
        Enhanced RTSP test with better error reporting
        """
        if not self.rtsp_url:
            return False, "No RTSP URL provided"

        # Build the complete URL considering all fields
        actual_url = self._build_complete_rtsp_url()

        cap = None
        try:
            print(f"Testing RTSP URL: {actual_url}")

            # Set OpenCV to use FFMPEG with specific options
            cap = cv2.VideoCapture(actual_url, cv2.CAP_FFMPEG)

            # Set timeouts
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)  # 10 seconds
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)   # 10 seconds

            if not cap.isOpened():
                return False, "Failed to initialize stream capture"

            # Try to read a frame
            ret, frame = cap.read()

            if ret and frame is not None:
                self.is_active = True
                self.last_stream_check = datetime.utcnow()
                db.session.commit()
                return True, f"Success! Frame size: {frame.shape[1]}x{frame.shape[0]}"
            else:
                self.is_active = False
                db.session.commit()
                return False, "Connected but could not read frame (stream may be offline)"

        except Exception as e:
            self.is_active = False
            db.session.commit()
            return False, f"Connection error: {str(e)}"
        finally:
            if cap:
                cap.release()

    def _build_complete_rtsp_url(self):
        """
        Build the complete RTSP URL from individual fields if they exist
        """
        # If rtsp_url is already complete, use it
        if self.rtsp_url and ('://' in self.rtsp_url):
            return self.rtsp_url

        # Otherwise build from components
        protocol = getattr(self, 'stream_protocol', 'rtsp') or 'rtsp'
        host = getattr(self, 'ip_address', '') or getattr(self, 'host', '')
        port = getattr(self, 'port', 554) or 554
        path = getattr(self, 'stream_path', '') or ''
        username = getattr(self, 'username', '')
        password = getattr(self, 'password', '')

        # Build URL
        if username and password:
            auth = f"{username}:{password}@"
        else:
            auth = ""

        if path and not path.startswith('/'):
            path = '/' + path

        return f"{protocol}://{auth}{host}:{port}{path}"
    
    def convert_rtsp_to_hls(self):
        """
        Convert RTSP stream to HLS format for web playback
        Returns the HLS stream URL if successful
        """
        # Build the RTSP URL with credentials
        auth_url = self._build_complete_rtsp_url()
        
        # Output directory for HLS segments
        output_dir = os.path.join(current_app.root_path, "static", "streams", str(self.id))
        os.makedirs(output_dir, exist_ok=True)
        
        # HLS playlist path
        playlist_path = os.path.join(output_dir, "stream.m3u8")
        
        # Check if FFmpeg is available
        if not shutil.which("ffmpeg"):
            return None, "FFmpeg not installed on server"
        
        # Build FFmpeg command
        cmd = [
            'ffmpeg',
            '-i', auth_url,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-hls_time', '2',
            '-hls_list_size', '5',
            '-hls_wrap', '10',
            '-start_number', '1',
            '-hls_segment_filename', os.path.join(output_dir, 'segment%03d.ts'),
            '-f', 'hls',
            playlist_path
        ]
        
        try:
            # Start the process in background
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Store process ID for later management
            self.stream_process_pid = process.pid
            db.session.commit()
            
            # Wait a moment for the stream to initialize
            time.sleep(2)
            
            # Check if playlist was created
            if os.path.exists(playlist_path):
                return f"/static/streams/{self.id}/stream.m3u8", None
            else:
                return None, "HLS playlist not created"
                
        except Exception as e:
            return None, f"FFmpeg error: {str(e)}"
    
    def stop_hls_conversion(self):
        """Stop the HLS conversion process"""
        if self.stream_process_pid:
            try:
                # Kill the process group
                os.killpg(os.getpgid(self.stream_process_pid), 9)
                self.stream_process_pid = None
                db.session.commit()
                return True
            except:
                self.stream_process_pid = None
                db.session.commit()
                return False
        return True
    
    def get_hls_stream_url(self):
        """Get or create HLS stream URL"""
        stream_path = os.path.join(current_app.root_path, "static", "streams", str(self.id), "stream.m3u8")
        
        # If stream doesn't exist or is stale, create it
        if not os.path.exists(stream_path) or \
           (self.last_stream_check and (datetime.utcnow() - self.last_stream_check).seconds > 300):
            return self.convert_rtsp_to_hls()[0]
        
        return f"/static/streams/{self.id}/stream.m3u8"
    
    # Add this diagnostic method to your Camera model
    def diagnose_connection_issues(self):
        """
        Run diagnostics to identify common RTSP issues
        """
        issues = []

        # Check if URL is provided
        if not self.rtsp_url and not hasattr(self, 'ip_address'):
            issues.append("No stream URL or IP address provided")
            return issues

        # Check network connectivity
        import socket
        try:
            host = self._extract_host_from_url()
            socket.gethostbyname(host)
        except socket.gaierror:
            issues.append(f"Cannot resolve hostname: {host}")

        # Check port accessibility
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, self.port or 554))
            if result != 0:
                issues.append(f"Port {self.port or 554} is not accessible")
            sock.close()
        except Exception as e:
            issues.append(f"Port test failed: {str(e)}")

        return issues

    def _extract_host_from_url(self):
        """Extract host from RTSP URL"""
        if self.rtsp_url and '://' in self.rtsp_url:
            from urllib.parse import urlparse
            parsed = urlparse(self.rtsp_url)
            return parsed.hostname or parsed.netloc.split('@')[-1].split(':')[0]
        return getattr(self, 'ip_address', '')