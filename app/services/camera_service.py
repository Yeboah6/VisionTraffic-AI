# import cv2
# import threading
# import time
# from typing import Dict, List, Optional
# import json
# from datetime import datetime

# class CameraService:
#     def __init__(self):
#         self.real_cameras = {}  # Active real camera connections
#         self.virtual_cameras = {}  # SUMO detector mappings
#         self.camera_data_buffer = {}  # Last 5 minutes of data
#         self.is_processing = False
        
#     def add_real_camera(self, camera_id: str, source: str, location: Dict):
#         """Add a real camera feed"""
#         self.real_cameras[camera_id] = {
#             'source': source,  # URL or RTSP stream
#             'location': location,  # {lat, lng, intersection_id}
#             'last_frame': None,
#             'metrics': {},
#             'is_active': False
#         }
    
#     def add_virtual_camera(self, camera_id: str, sumo_detector_id: str, location: Dict):
#         """Add SUMO virtual camera (detector)"""
#         self.virtual_cameras[camera_id] = {
#             'detector_id': sumo_detector_id,
#             'location': location,
#             'type': 'virtual'
#         }
    
#     def start_real_camera_processing(self, camera_id: str):
#         """Start processing real camera feed"""
#         if camera_id in self.real_cameras:
#             thread = threading.Thread(target=self._process_camera_feed, args=(camera_id,))
#             thread.daemon = True
#             thread.start()
    
#     def _process_camera_feed(self, camera_id: str):
#         """Process real camera feed with computer vision"""
#         camera = self.real_cameras[camera_id]
#         cap = cv2.VideoCapture(camera['source'])
        
#         while self.is_processing and camera_id in self.real_cameras:
#             ret, frame = cap.read()
#             if ret:
#                 # Computer vision processing
#                 metrics = self._analyze_frame(frame)
                
#                 # Store processed data (not raw frame)
#                 self._store_camera_metrics(camera_id, metrics)
                
#                 # Update last frame for visualization
#                 camera['last_frame'] = self._frame_to_json(frame)
#                 camera['metrics'] = metrics
                
#             time.sleep(0.1)  # ~10 FPS processing
    
#     def _analyze_frame(self, frame) -> Dict:
#         """Analyze camera frame and extract traffic metrics"""
#         # Simplified computer vision - replace with YOLO/OpenCV
#         return {
#             'vehicle_count': self._count_vehicles_simple(frame),
#             'average_speed': self._estimate_speed(frame),
#             'queue_length': self._detect_queues(frame),
#             'congestion_level': self._assess_congestion(frame),
#             'timestamp': datetime.utcnow().isoformat()
#         }
    
#     def get_sumo_virtual_camera_data(self, traci_connection) -> Dict:
#         """Get data from SUMO virtual cameras (detectors)"""
#         virtual_data = {}
        
#         for cam_id, camera_info in self.virtual_cameras.items():
#             detector_id = camera_info['detector_id']
#             try:
#                 vehicle_count = traci_connection.lanearea.getLastStepVehicleNumber(detector_id)
#                 speed = traci_connection.lanearea.getLastStepMeanSpeed(detector_id)
                
#                 virtual_data[cam_id] = {
#                     'vehicle_count': vehicle_count,
#                     'average_speed': speed,
#                     'queue_length': self._calculate_sumo_queue(detector_id, traci_connection),
#                     'timestamp': datetime.utcnow().isoformat(),
#                     'source': 'virtual'
#                 }
#             except:
#                 virtual_data[cam_id] = {'error': 'Detector not found', 'source': 'virtual'}
        
#         return virtual_data
    
#     def get_combined_camera_data(self, traci_connection = None) -> Dict:
#         """Get data from both real and virtual cameras"""
#         combined_data = {}
        
#         # Real camera data
#         for cam_id, camera in self.real_cameras.items():
#             if camera.get('metrics'):
#                 combined_data[cam_id] = {
#                     **camera['metrics'],
#                     'source': 'real',
#                     'location': camera['location']
#                 }
        
#         # Virtual camera data (if SUMO connection available)
#         if traci_connection:
#             virtual_data = self.get_sumo_virtual_camera_data(traci_connection)
#             combined_data.update(virtual_data)
        
#         return combined_data
    
#     def _store_camera_metrics(self, camera_id: str, metrics: Dict):
#         """Store camera metrics in buffer"""
#         if camera_id not in self.camera_data_buffer:
#             self.camera_data_buffer[camera_id] = []
        
#         self.camera_data_buffer[camera_id].append(metrics)
        
#         # Keep only last 5 minutes of data (~300 records at 1 FPS)
#         if len(self.camera_data_buffer[camera_id]) > 300:
#             self.camera_data_buffer[camera_id].pop(0)

# # Global instance
# camera_service = CameraService()