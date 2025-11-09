import traci
import time
import random
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from app.extensions import db
from app.services.db_queue import db_queue_service

class EmergencyService:
    """
    Simplified emergency vehicle service using direct TraCI detection
    """
    
    def __init__(self, app=None):
        self.app = app
        
        # Simple emergency vehicle patterns
        self.emergency_patterns = [
            'ambulance', 'emergency', 'fire', 'police', 'rescue', 
            'paramedic', 'hospital', 'sheriff', 'patrol'
        ]
        
        # Active tracking
        self.active_emergencies = {}
        self.emergency_registry = {}  # Simple registry
        self.last_vehicle_states = {}
        
        # Statistics
        self.stats = {
            'detected_emergencies': 0,
            'active_emergencies': 0,
            'green_waves_activated': 0
        }
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def initialize_emergency_registry(self, traci):
        """
        SIMPLE APPROACH: Scan current vehicles and create registry
        """
        print("🚨 INITIALIZING EMERGENCY VEHICLE REGISTRY...")
        
        try:
            vehicle_ids = traci.vehicle.getIDList()
            registered_count = 0
            
            for vehicle_id in vehicle_ids:
                if self._is_emergency_vehicle(traci, vehicle_id):
                    # Add to registry
                    self._register_emergency_vehicle(traci, vehicle_id)
                    registered_count += 1
            
            print(f"✅ Emergency registry initialized: {registered_count} vehicles found")
            
        except Exception as e:
            print(f"❌ Emergency registry initialization failed: {e}")
            
    def _preload_emergency_schedule_to_db(self, traci):
        """Store emergency vehicle registry directly to database"""
        print("💾 Creating emergency vehicle registry from simulation...")

        stored_count = 0
        try:
            # Get all vehicles currently in simulation
            vehicle_ids = traci.vehicle.getIDList()

            for vehicle_id in vehicle_ids:
                if self._is_emergency_vehicle(traci, vehicle_id):
                    try:
                        # Get complete route information using TraCI
                        route_info = self._get_vehicle_route_info(traci, vehicle_id)

                        # Create the emergency registry entry directly in database
                        success = self._save_emergency_registry_to_db(route_info)

                        if success:
                            stored_count += 1
                            # Also add to local registry for real-time tracking
                            self.emergency_registry[vehicle_id] = route_info

                            print(f"📅 Registered emergency: {vehicle_id} as {route_info['emergency_type']}")

                    except Exception as e:
                        print(f"⚠️ Failed to register emergency vehicle {vehicle_id}: {e}")

            print(f"✅ Successfully registered {stored_count} emergency vehicles in database")

        except Exception as e:
            print(f"❌ Error creating emergency registry: {e}")
    
    def _manage_emergency_vehicles_simple(self, traci, current_time: float):
        """Continuous emergency vehicle management"""
        try:
            # Initialize emergency service if not already done
            if not hasattr(self, 'emergency_service_initialized'):
                from app.services.emergency import emergency_service
                self.emergency_service = emergency_service
                self.emergency_service.init_app(self.app)
                self.emergency_service_initialized = True
                print("🚨 Emergency service initialized")

            # CONTINUOUS REGISTRY UPDATE - check for new vehicles every cycle
            new_emergencies_found = self.emergency_service.update_emergency_registry(traci, self.current_config)

            if new_emergencies_found:
                print(f"🚨 Found {new_emergencies_found} new emergency vehicles")

            # 1. Detect emergency vehicles in real-time
            detected_emergencies = self.emergency_service.detect_emergency_vehicles(traci)

            # 2. Get vehicles that need green waves
            green_wave_candidates = self.emergency_service.get_green_wave_candidates(traci, current_time)

            # 3. Apply green waves for approaching emergencies
            if green_wave_candidates:
                self._apply_simple_green_waves(traci, green_wave_candidates)

            # 4. Store emergency vehicle data
            if detected_emergencies:
                self.emergency_service.store_emergency_data(detected_emergencies, current_time, self.current_config)

            # 5. Update monitoring data
            self.monitoring_data['emergency_vehicles'] = {
                'detected_emergencies': detected_emergencies,
                'green_wave_candidates': green_wave_candidates,
                'active_count': len(detected_emergencies),
                'registry_count': len(self.emergency_service.emergency_registry),
                'timestamp': time.time()
            }

        except Exception as e:
            print(f"⚠️ Emergency management error: {e}")        
    
    def update_emergency_registry(self, traci, scenario: str) -> int:
        """Continuously update emergency vehicle registry with new vehicles"""
        new_registrations = 0
        
        try:
            vehicle_ids = traci.vehicle.getIDList()
            
            for vehicle_id in vehicle_ids:
                # Check if this is an emergency vehicle not yet registered
                if (vehicle_id not in self.emergency_registry and 
                    self._is_emergency_vehicle(traci, vehicle_id)):
                    
                    try:
                        # Get route information
                        route_info = self._get_vehicle_route_info(traci, vehicle_id)
                        
                        # Save to database
                        success = self._save_emergency_registry_to_db(route_info, scenario)
                        
                        if success:
                            self.emergency_registry[vehicle_id] = route_info
                            new_registrations += 1
                            print(f"📝 New emergency registered: {vehicle_id}")
                            
                    except Exception as e:
                        print(f"⚠️ Failed to register new emergency {vehicle_id}: {e}")
            
            return new_registrations
            
        except Exception as e:
            print(f"❌ Error updating emergency registry: {e}")
            return 0
    
    def _save_emergency_registry_to_db(self, route_info: Dict) -> bool:
        """Save emergency vehicle registry directly to database"""
        if not self.app:
            print("⚠️ No app context for database operations")
            return False

        try:
            with self.app.app_context():
                from app.models.emergency_veh import EmergencyVehicleRegistry

                # Check if registry entry already exists
                existing_registry = EmergencyVehicleRegistry.query.filter_by(
                    vehicle_id=route_info['vehicle_id'],
                    scenario=self.current_config or 'default_simulation'
                ).first()

                if existing_registry:
                    # Update existing registry
                    existing_registry.vehicle_type = route_info['emergency_type']
                    existing_registry.original_type = route_info.get('original_type', '')
                    existing_registry.scheduled_departure = route_info['departure_time']
                    existing_registry.from_edge = route_info['route_edges'][0] if route_info['route_edges'] else ''
                    existing_registry.to_edge = route_info['route_edges'][-1] if route_info['route_edges'] else ''
                    existing_registry.route_edges = json.dumps(route_info['route_edges'])
                    existing_registry.estimated_arrival_time = json.dumps(route_info['estimated_arrival_times'])
                    existing_registry.status = 'ACTIVE'
                    existing_registry.details = route_info
                    action = "updated"
                else:
                    # Create new registry entry
                    new_registry = EmergencyVehicleRegistry(
                        id=f"registry_{route_info['vehicle_id']}_{int(time.time())}",
                        scenario=self.current_config or 'default_simulation',
                        vehicle_id=route_info['vehicle_id'],
                        vehicle_type=route_info['emergency_type'],
                        original_type=route_info.get('original_type', ''),
                        scheduled_departure=route_info['departure_time'],
                        from_edge=route_info['route_edges'][0] if route_info['route_edges'] else '',
                        to_edge=route_info['route_edges'][-1] if route_info['route_edges'] else '',
                        route_edges=json.dumps(route_info['route_edges']),
                        estimated_arrival_time=json.dumps(route_info['estimated_arrival_times']),
                        status='ACTIVE',
                        details=route_info
                    )
                    db.session.add(new_registry)
                    action = "created"

                db.session.commit()
                print(f"✅ Emergency registry {action} for {route_info['vehicle_id']}")
                return True

        except Exception as e:
            print(f"❌ Error saving emergency registry to database: {e}")
            db.session.rollback()
            return False

    def _get_vehicle_route_info(self, traci, vehicle_id: str) -> Dict[str, Any]:
        """Get complete route information for a vehicle using TraCI"""
        try:
            # Get basic vehicle info
            vehicle_type = traci.vehicle.getTypeID(vehicle_id)
            vehicle_class = traci.vehicle.getVehicleClass(vehicle_id)

            # Get current position and route
            current_lane = traci.vehicle.getLaneID(vehicle_id)
            current_road = traci.vehicle.getRoadID(vehicle_id)
            route_edges = traci.vehicle.getRoute(vehicle_id)

            # Get emergency type
            emergency_type = self._classify_emergency_type(vehicle_type, vehicle_class, vehicle_id)

            # Estimate arrival times at traffic lights along the route
            estimated_arrival_times = self._estimate_route_arrival_times(traci, vehicle_id, route_edges)

            # Get departure time (current simulation time)
            departure_time = traci.simulation.getTime()

            return {
                'vehicle_id': vehicle_id,
                'emergency_type': emergency_type,
                'original_type': vehicle_type,
                'vehicle_class': vehicle_class,
                'departure_time': departure_time,
                'route_edges': route_edges,
                'current_lane': current_lane,
                'current_road': current_road,
                'estimated_arrival_times': estimated_arrival_times,
                'priority': self._classify_priority(emergency_type)
            }

        except Exception as e:
            print(f"❌ Error getting route info for {vehicle_id}: {e}")
            # Return basic info if detailed route info fails
            return {
                'vehicle_id': vehicle_id,
                'emergency_type': 'EMERGENCY',
                'original_type': traci.vehicle.getTypeID(vehicle_id),
                'vehicle_class': traci.vehicle.getVehicleClass(vehicle_id),
                'departure_time': traci.simulation.getTime(),
                'route_edges': [],
                'current_lane': 'unknown',
                'current_road': 'unknown',
                'estimated_arrival_times': {},
                'priority': 'MEDIUM'
            }

    def _estimate_route_arrival_times(self, traci, vehicle_id: str, route_edges: List[str]) -> Dict[str, float]:
        """Estimate arrival times at traffic lights along the route"""
        arrival_times = {}
        current_time = traci.simulation.getTime()
        current_speed = traci.vehicle.getSpeed(vehicle_id)

        # Get vehicle's current position in route
        try:
            current_road = traci.vehicle.getRoadID(vehicle_id)
            if current_road in route_edges:
                current_index = route_edges.index(current_road)
                remaining_edges = route_edges[current_index:]
            else:
                remaining_edges = route_edges
        except:
            remaining_edges = route_edges

        # Calculate arrival times for each traffic light in remaining route
        accumulated_time = 0.0

        for edge in remaining_edges:
            # Estimate travel time for this edge
            edge_travel_time = self._estimate_edge_travel_time(traci, edge, current_speed)
            accumulated_time += edge_travel_time

            # Check if this edge has a traffic light
            tls_id = self._get_traffic_light_for_edge(traci, edge)
            if tls_id and tls_id not in arrival_times:
                arrival_time = current_time + accumulated_time
                arrival_times[tls_id] = arrival_time

                # Add intersection approach time
                accumulated_time += 2.0  # 2 seconds for intersection approach

        return arrival_times

    def _estimate_edge_travel_time(self, traci, edge_id: str, current_speed: float) -> float:
        """Estimate travel time for an edge"""
        try:
            # Get edge length from TraCI
            edge_length = traci.lane.getLength(edge_id + '_0')  # Assume first lane
            speed = max(current_speed, 5.0)  # Minimum speed of 5 m/s
            return edge_length / speed
        except:
            # Fallback estimation
            return 10.0  # Default 10 seconds per edge

    def _get_traffic_light_for_edge(self, traci, edge_id: str) -> Optional[str]:
        """Get traffic light controlling an edge"""
        try:
            # Get all traffic lights
            tl_ids = traci.trafficlight.getIDList()

            for tl_id in tl_ids:
                # Get lanes controlled by this traffic light
                controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)

                # Check if our edge is among the controlled lanes
                for lane in controlled_lanes:
                    if lane.startswith(edge_id + '_'):
                        return tl_id

            return None
        except:
            return None
    
    def _is_emergency_vehicle(self, traci, vehicle_id: str) -> bool:
        """Simple check if vehicle is emergency"""
        try:
            vehicle_type = traci.vehicle.getTypeID(vehicle_id)
            vehicle_class = traci.vehicle.getVehicleClass(vehicle_id)
            
            # Convert to lowercase for pattern matching
            vehicle_id_lower = vehicle_id.lower()
            vehicle_type_lower = vehicle_type.lower() if vehicle_type else ''
            vehicle_class_lower = vehicle_class.lower() if vehicle_class else ''
            
            # Check patterns
            id_match = any(pattern in vehicle_id_lower for pattern in self.emergency_patterns)
            type_match = any(pattern in vehicle_type_lower for pattern in self.emergency_patterns)
            class_match = vehicle_class in ['emergency', 'authority', 'vip']
            
            return id_match or type_match or class_match
            
        except Exception as e:
            return False
    
    def _register_emergency_vehicle(self, traci, vehicle_id: str):
        """Register an emergency vehicle"""
        try:
            vehicle_type = traci.vehicle.getTypeID(vehicle_id)
            vehicle_class = traci.vehicle.getVehicleClass(vehicle_id)
            
            emergency_type = self._classify_emergency_type(vehicle_type, vehicle_class, vehicle_id)
            
            self.emergency_registry[vehicle_id] = {
                'vehicle_id': vehicle_id,
                'vehicle_type': emergency_type,
                'original_type': vehicle_type,
                'vehicle_class': vehicle_class,
                'registered_at': time.time(),
                'priority': self._classify_priority(emergency_type)
            }
            
            print(f"📝 Registered emergency: {vehicle_id} as {emergency_type}")
            
        except Exception as e:
            print(f"❌ Failed to register emergency vehicle {vehicle_id}: {e}")
    
    def detect_emergency_vehicles(self, traci) -> List[Dict]:
        """
        Real-time emergency vehicle detection with route awareness
        """
        emergencies = []

        try:
            # Check registered emergencies first
            for vehicle_id, registry_info in self.emergency_registry.items():
                if vehicle_id in traci.vehicle.getIDList():
                    emergency_data = self._create_emergency_record(traci, vehicle_id, registry_info)
                    if emergency_data:
                        emergencies.append(emergency_data)
                else:
                    # Vehicle no longer in simulation, remove from registry
                    del self.emergency_registry[vehicle_id]

            # Check for new emergency vehicles
            vehicle_ids = traci.vehicle.getIDList()
            for vehicle_id in vehicle_ids:
                if (vehicle_id not in self.emergency_registry and 
                    self._is_emergency_vehicle(traci, vehicle_id)):

                    # Register new emergency vehicle
                    route_info = self._get_vehicle_route_info(traci, vehicle_id)
                    self.emergency_registry[vehicle_id] = route_info

                    emergency_data = self._create_emergency_record(traci, vehicle_id, route_info)
                    if emergency_data:
                        emergencies.append(emergency_data)
                        print(f"🚨 NEW EMERGENCY REGISTERED: {vehicle_id}")

            # Update active emergencies
            self.active_emergencies = {e['vehicle_id']: e for e in emergencies}
            self.stats['active_emergencies'] = len(emergencies)

            return emergencies

        except Exception as e:
            print(f"❌ Emergency detection failed: {e}")
            return []
    
    def _create_emergency_record(self, traci, vehicle_id: str, registry_info: Dict) -> Optional[Dict]:
        """Create emergency record with current position and route data"""
        try:
            # Get current vehicle state
            speed = traci.vehicle.getSpeed(vehicle_id)
            lane_id = traci.vehicle.getLaneID(vehicle_id)
            road_id = traci.vehicle.getRoadID(vehicle_id)

            # Get next traffic light with updated timing
            next_tls = traci.vehicle.getNextTLS(vehicle_id)
            distance_to_tls = 0
            time_to_tls = 0
            controlling_tls = None

            if next_tls:
                next_tls_info = next_tls[0]
                controlling_tls = next_tls_info[0]
                distance_to_tls = next_tls_info[2]
                time_to_tls = distance_to_tls / max(speed, 0.1) if speed > 0 else 999

            # Combine registry info with current state
            return {
                'vehicle_id': vehicle_id,
                'vehicle_type': registry_info.get('emergency_type', 'EMERGENCY'),
                'original_type': registry_info.get('original_type', ''),
                'vehicle_class': registry_info.get('vehicle_class', ''),
                'traffic_light_id': controlling_tls or 'unknown',
                'lane_id': lane_id,
                'road_id': road_id,
                'speed': speed,
                'distance_to_intersection': distance_to_tls,
                'time_to_intersection': time_to_tls,
                'priority': registry_info.get('priority', 'MEDIUM'),
                'is_registered': True,
                'route_edges': registry_info.get('route_edges', []),
                'estimated_arrivals': registry_info.get('estimated_arrival_times', {}),
                'timestamp': time.time(),
                'detected_at': datetime.utcnow(),
            }

        except Exception as e:
            print(f"⚠️ Could not create emergency record for {vehicle_id}: {e}")
            return None
    
    def get_green_wave_candidates(self, traci, current_time: float) -> List[Dict]:
        """
        Get emergency vehicles that need green waves with route-based timing
        """
        candidates = []

        for vehicle_id, emergency in self.active_emergencies.items():
            # Use both real-time proximity and scheduled arrival times
            real_time_proximity = emergency.get('time_to_intersection', 999) <= 12.0
            scheduled_arrival = self._check_scheduled_arrival(emergency, current_time)

            if (real_time_proximity or scheduled_arrival) and emergency.get('traffic_light_id') != 'unknown':
                candidates.append({
                    'vehicle_id': vehicle_id,
                    'traffic_light_id': emergency['traffic_light_id'],
                    'time_to_intersection': emergency['time_to_intersection'],
                    'scheduled_arrival': scheduled_arrival,
                    'priority': emergency['priority'],
                    'current_speed': emergency['speed'],
                    'route_edges': emergency.get('route_edges', [])
                })

        return candidates
    
    def _check_scheduled_arrival(self, emergency: Dict, current_time: float) -> bool:
        """Check if vehicle is approaching a scheduled arrival time"""
        estimated_arrivals = emergency.get('estimated_arrivals', {})

        for tl_id, arrival_time in estimated_arrivals.items():
            time_until_arrival = arrival_time - current_time
            if 0 <= time_until_arrival <= 20.0:  # 20 seconds before scheduled arrival
                return True

        return False
    
    def store_emergency_data(self, emergencies: List[Dict], current_time: float, scenario: str):
        """Store emergency vehicle data with change detection"""
        if not emergencies:
            return
        
        emergencies_to_store = []
        
        for emergency in emergencies:
            vehicle_id = emergency['vehicle_id']
            
            # Simple change detection - store if significant change or first time
            if self._should_store_emergency(vehicle_id, emergency):
                emergencies_to_store.append(emergency)
        
        if emergencies_to_store:
            print(f"💾 Storing {len(emergencies_to_store)} emergency records...")
            
            for emergency in emergencies_to_store:
                try:
                    emergency_data = {
                        'id': f"emergency_{int(current_time)}_{random.randint(1000, 9999)}",
                        'scenario': scenario,
                        'vehicle_id': emergency['vehicle_id'],
                        'vehicle_type': emergency['vehicle_type'],
                        'original_type': emergency.get('original_type', ''),
                        'vehicle_class': emergency.get('vehicle_class', ''),
                        'traffic_light_id': emergency['traffic_light_id'],
                        'lane_id': emergency['lane_id'],
                        'road_id': emergency.get('road_id', ''),
                        'speed': emergency['speed'],
                        'distance_to_intersection': emergency['distance_to_intersection'],
                        'time_to_intersection': emergency['time_to_intersection'],
                        'priority': emergency['priority'],
                        'is_registered': emergency.get('is_registered', False),
                        'detected_at': emergency.get('detected_at', datetime.utcnow()),
                        'scenario_timestamp': current_time,
                        'details': emergency
                    }
                    
                    if hasattr(db_queue_service, 'add_emergency_log'):
                        db_queue_service.add_emergency_log(emergency_data)
                        
                except Exception as e:
                    print(f"❌ Failed to store emergency data: {e}")
    
    def _should_store_emergency(self, vehicle_id: str, current_emergency: Dict) -> bool:
        """Simple change detection for emergency vehicles"""
        if vehicle_id not in self.last_vehicle_states:
            self.last_vehicle_states[vehicle_id] = current_emergency
            return True
        
        last_state = self.last_vehicle_states[vehicle_id]
        
        # Store if significant position change or time elapsed
        position_change = abs(current_emergency.get('distance_to_intersection', 0) - 
                             last_state.get('distance_to_intersection', 0))
        
        time_elapsed = time.time() - last_state.get('timestamp', 0)
        
        if position_change > 10.0 or time_elapsed > 30.0:
            self.last_vehicle_states[vehicle_id] = current_emergency
            return True
        
        return False
    
    def _classify_emergency_type(self, vehicle_type: str, vehicle_class: str, vehicle_id: str) -> str:
        """Classify emergency type"""
        combined = (vehicle_id + ' ' + (vehicle_type or '') + ' ' + (vehicle_class or '')).lower()
        
        if any(indicator in combined for indicator in ['ambulance', 'medic', 'hospital', 'paramedic']):
            return 'AMBULANCE'
        elif any(indicator in combined for indicator in ['fire', 'firefighter', 'fire_engine']):
            return 'FIRE_TRUCK'
        elif any(indicator in combined for indicator in ['police', 'sheriff', 'patrol']):
            return 'POLICE'
        else:
            return 'EMERGENCY'
    
    def _classify_priority(self, emergency_type: str) -> str:
        """Classify emergency priority"""
        if emergency_type == 'AMBULANCE':
            return 'CRITICAL'
        elif emergency_type in ['FIRE_TRUCK', 'POLICE']:
            return 'HIGH'
        else:
            return 'MEDIUM'
    
    def get_stats(self) -> Dict[str, Any]:
        """Get emergency service statistics"""
        return {
            **self.stats,
            'registered_emergencies': len(self.emergency_registry),
            'active_emergencies_count': len(self.active_emergencies)
        }

# Global instance
emergency_service = EmergencyService()