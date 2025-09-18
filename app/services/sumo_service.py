import traci
import sumolib
import threading
import time
import json
from datetime import datetime
from flask import current_app
import numpy as np

class SUMOService:
    def __init__(self, app=None):
        self.simulation_running = False
        self.sim_thread = None
        self.current_step = 0
        self.vehicles_data = {}
        self.traffic_lights_data = {}
        self.simulation_stats = {}
        self.ai_controller = None
        
        self._last_status_time = 0
        self._last_stop_time = datetime.now()  # Initialize with current time
        self._status_request_count = 0
        self._status_cache = None
        self._status_cache_time = 0
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        self.config = app.config
        self.sumo_config = app.config.get('SUMO_CONFIG', 'sumo_configs/Traci.sumocfg')
    
    def set_ai_controller(self, ai_controller):
        """Set the AI controller for automated traffic management"""
        self.ai_controller = ai_controller
    
    def start_simulation(self, config_file=None):
        """Start SUMO simulation in a separate thread"""
        if config_file:
            self.sumo_config = config_file
            
        def run_simulation():
            try:
                # Start SUMO with TraCI connection
                sumo_binary = self.config.get('SUMO_BINARY', 'sumo')
                traci.start([sumo_binary, "-c", self.sumo_config, "--start"])
                self.simulation_running = True
                self.current_step = 0
                self.simulation_stats = {
                    'start_time': datetime.now(),
                    'total_vehicles': 0,
                    'total_co2': 0,
                    'total_fuel': 0,
                    'avg_speed': 0,
                    'congestion_level': 0
                }
                
                # Clear cache when starting new simulation
                self._status_cache = None
                
                while self.simulation_running and traci.simulation.getMinExpectedNumber() > 0:
                    traci.simulationStep()
                    self.current_step += 1
                    self._collect_simulation_data()
                    
                    # Apply AI control if available
                    if self.ai_controller and self.current_step % 10 == 0:  # Apply AI every 10 steps
                        self._apply_ai_control()
                    
                    # Slow down simulation if needed
                    time.sleep(self.config.get('SUMO_SIMULATION_DELAY', 0.1))
                    
                self.simulation_running = False
                self._last_stop_time = datetime.now()
                traci.close()
                
            except Exception as e:
                current_app.logger.error(f"SUMO simulation error: {str(e)}")
                self.simulation_running = False
                self._last_stop_time = datetime.now()
        
        if not self.simulation_running:
            self.sim_thread = threading.Thread(target=run_simulation)
            self.sim_thread.daemon = True
            self.sim_thread.start()
            return True
        return False
    
    def _apply_ai_control(self):
        """Apply AI control to the simulation"""
        try:
            # Get current simulation state for AI
            current_state = self.get_current_state()
            
            # Let AI make decisions
            ai_decisions = self.ai_controller.make_decisions(current_state)
            
            # Apply AI decisions
            for decision in ai_decisions:
                if decision['type'] == 'traffic_light_control':
                    self.control_traffic_light(
                        decision['tl_id'], 
                        decision['state'], 
                        decision.get('duration')
                    )
                elif decision['type'] == 'vehicle_reroute':
                    self.reroute_vehicle(
                        decision['vehicle_id'], 
                        decision['new_route']
                    )
                    
        except Exception as e:
            current_app.logger.error(f"AI control error: {str(e)}")
    
    def _collect_simulation_data(self):
        """Collect data from the current simulation step"""
        # Vehicle data
        vehicle_ids = traci.vehicle.getIDList()
        self.vehicles_data[self.current_step] = {}
        
        total_speed = 0
        total_co2 = 0
        total_fuel = 0
        
        for veh_id in vehicle_ids:
            vehicle_data = {
                "position": traci.vehicle.getPosition(veh_id),
                "speed": traci.vehicle.getSpeed(veh_id),
                "angle": traci.vehicle.getAngle(veh_id),
                "route": traci.vehicle.getRoute(veh_id),
                "lane": traci.vehicle.getLaneID(veh_id),
                "type": traci.vehicle.getTypeID(veh_id),
                "co2_emission": traci.vehicle.getCO2Emission(veh_id),
                "fuel_consumption": traci.vehicle.getFuelConsumption(veh_id),
                "waiting_time": traci.vehicle.getWaitingTime(veh_id),
            }
            
            self.vehicles_data[self.current_step][veh_id] = vehicle_data
            
            # Update statistics
            total_speed += vehicle_data['speed']
            total_co2 += vehicle_data['co2_emission']
            total_fuel += vehicle_data['fuel_consumption']
        
        # Update simulation statistics
        vehicle_count = len(vehicle_ids)
        self.simulation_stats['total_vehicles'] = max(self.simulation_stats['total_vehicles'], vehicle_count)
        self.simulation_stats['total_co2'] += total_co2
        self.simulation_stats['total_fuel'] += total_fuel
        self.simulation_stats['avg_speed'] = total_speed / vehicle_count if vehicle_count > 0 else 0
        self.simulation_stats['congestion_level'] = self._calculate_congestion_level(vehicle_count)
        
        # Traffic light data
        tl_ids = traci.trafficlight.getIDList()
        self.traffic_lights_data[self.current_step] = {}
        
        for tl_id in tl_ids:
            self.traffic_lights_data[self.current_step][tl_id] = {
                "state": traci.trafficlight.getRedYellowGreenState(tl_id),
                "phase": traci.trafficlight.getPhase(tl_id),
                "program": traci.trafficlight.getProgram(tl_id),
            }
    
    def _calculate_congestion_level(self, vehicle_count):
        """Calculate congestion level based on vehicle count and road capacity"""
        # Simplified congestion calculation
        # In a real implementation, this would consider road capacity and network topology
        max_vehicles = 100  # Example maximum capacity
        return min(vehicle_count / max_vehicles * 3, 3)  # Scale to 0-3
    
    def stop_simulation(self):
        """Stop the running simulation and record stop time"""
        self.simulation_running = False
        self._last_stop_time = datetime.now()
        
        # Clear status cache
        self._status_cache = None
        
        if self.sim_thread:
            self.sim_thread.join(timeout=5.0)
        return True
    
    def get_current_state(self):
        """Get the current state of the simulation with efficiency optimizations"""
        if not self.simulation_running:
            # Check if we've recently stopped to avoid immediate status requests after stopping
            if hasattr(self, '_last_stop_time'):
                time_since_stop = (datetime.now() - self._last_stop_time).total_seconds()
                
                # Return cached data if recently stopped
                if time_since_stop < 2:
                    return {
                        "status": "not_running",
                        "step": self.current_step,
                        "vehicles": self.vehicles_data.get(self.current_step, {}),
                        "traffic_lights": self.traffic_lights_data.get(self.current_step, {}),
                        "statistics": self.simulation_stats,
                        "time": datetime.now().isoformat(),
                        "cached": True
                    }
            return {"status": "not_running"}
        
        current_time = time.time()
        
        # Use cached data if available and recent (within 0.5 seconds)
        if (self._status_cache and current_time - self._status_cache_time < 0.5):
            result = self._status_cache.copy()
            result["cached"] = True
            return result

        # Ensure latest data is collected for the current step
        if (self.current_step not in self.vehicles_data or 
            self.current_step not in self.traffic_lights_data):
            self._collect_simulation_data()

        # Implement rate limiting for high-frequency requests
        time_since_last = current_time - self._last_status_time
        if time_since_last < 0.1:  # Limit to 10 requests per second max
            # Return cached data if requested too frequently
            if self._status_cache:
                result = self._status_cache.copy()
                result["cached"] = True
                return result

        self._last_status_time = current_time

        # Prepare response
        result = {
            "status": "running",
            "step": self.current_step,
            "vehicles": self.vehicles_data.get(self.current_step, {}),
            "traffic_lights": self.traffic_lights_data.get(self.current_step, {}),
            "statistics": self.simulation_stats,
            "time": datetime.now().isoformat(),
            "cached": False
        }
        
        # Cache the result
        self._status_cache = result
        self._status_cache_time = current_time
        
        return result
    
    def get_lightweight_status(self):
        """Get a lightweight status for frequent polling"""
        if not self.simulation_running:
            return {"status": "not_running"}
        
        return {
            "status": "running",
            "step": self.current_step,
            "vehicle_count": len(self.vehicles_data.get(self.current_step, {})),
            "time": datetime.now().isoformat()
        }
        
    
    def control_traffic_light(self, tl_id, state, duration=None):
        """Control a traffic light"""
        if not self.simulation_running:
            return False
        
        try:
            if duration:
                traci.trafficlight.setPhaseDuration(tl_id, duration)
            traci.trafficlight.setRedYellowGreenState(tl_id, state)
            return True
        except:
            return False
    
    def reroute_vehicle(self, vehicle_id, new_route):
        """Reroute a vehicle"""
        if not self.simulation_running:
            return False
        
        try:
            traci.vehicle.setRoute(vehicle_id, new_route)
            return True
        except:
            return False
    
    def get_route_info(self, vehicle_id):
        """Get information about a vehicle's route"""
        if not self.simulation_running:
            return None
        
        try:
            return {
                "route": traci.vehicle.getRoute(vehicle_id),
                "edges": traci.vehicle.getRoute(vehicle_id),
                "next_tls": traci.vehicle.getNextTLS(vehicle_id)
            }
        except:
            return None
    
    def get_simulation_statistics(self):
        """Get simulation statistics"""
        if not self.simulation_running:
            return {"error": "Simulation not running"}
        
        # Calculate statistics based on collected data
        current_data = self.get_current_state()
        vehicles = current_data.get('vehicles', {})
        
        total_vehicles = len(vehicles)
        avg_speed = sum(v['speed'] for v in vehicles.values()) / total_vehicles if total_vehicles > 0 else 0
        total_co2 = sum(v['co2_emission'] for v in vehicles.values()) if total_vehicles > 0 else 0
        total_fuel = sum(v['fuel_consumption'] for v in vehicles.values()) if total_vehicles > 0 else 0
        avg_waiting_time = sum(v['waiting_time'] for v in vehicles.values()) / total_vehicles if total_vehicles > 0 else 0
        
        return {
            "total_vehicles": total_vehicles,
            "average_speed": round(avg_speed, 2),
            "total_co2_emission": round(total_co2, 2),
            "total_fuel_consumption": round(total_fuel, 2),
            "average_waiting_time": round(avg_waiting_time, 2),
            "congestion_level": round(self.simulation_stats.get('congestion_level', 0), 2),
            "simulation_step": self.current_step,
            "simulation_time": str(datetime.now() - self.simulation_stats.get('start_time', datetime.now()))
        }

# Create a global instance
sumo_service = SUMOService()