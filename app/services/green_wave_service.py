import time
from collections import defaultdict
from typing import Dict, List, Any


class GreenWaveService:
    """
    Green wave coordination service for SUMO traffic lights
    Creates coordinated green phases across multiple junctions for smooth traffic flow
    """
    
    def __init__(self, app=None):
        self.app = app
        self.coordination_groups = defaultdict(list)  # Group of coordinated TLS
        self.wave_progress = {}  # Track green wave progress
        self.coordination_enabled = True
        self.max_wave_distance = 500  # meters - maximum distance for coordination
        self.min_vehicle_count = 2  # Minimum vehicles to trigger green wave
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def analyze_network_conditions(self, tls_snapshot: Dict) -> Dict[str, Any]:
        """
        Analyze network-wide conditions to identify green wave opportunities
        """
        try:
            analysis = {
                'green_wave_opportunities': [],
                'coordinated_groups': [],
                'recommendations': [],
                'timestamp': time.time()
            }
            
            if not tls_snapshot or not tls_snapshot.get('traffic_lights'):
                return analysis
            
            tls_data = tls_snapshot['traffic_lights']
            
            # 1. Identify TLS pairs/groups that can form green waves
            coordination_groups = self._identify_coordination_groups(tls_data)
            analysis['coordinated_groups'] = coordination_groups
            
            # 2. Analyze each group for green wave potential
            for group_id, group_tls in coordination_groups.items():
                wave_opportunity = self._analyze_group_wave_potential(group_tls, tls_data)
                if wave_opportunity['feasible']:
                    analysis['green_wave_opportunities'].append(wave_opportunity)
                    analysis['recommendations'].append({
                        'group_id': group_id,
                        'action': 'ACTIVATE_GREEN_WAVE',
                        'direction': wave_opportunity['direction'],
                        'expected_benefit': wave_opportunity['expected_benefit']
                    })
            
            return analysis
            
        except Exception as e:
            print(f"❌ Green wave analysis error: {e}")
            return {'green_wave_opportunities': [], 'recommendations': []}
    
    def _identify_coordination_groups(self, tls_data: Dict) -> Dict[str, List]:
        """
        Identify groups of traffic lights that can be coordinated for green waves
        Based on proximity and road connectivity
        """
        coordination_groups = {}
        processed_tls = set()
        
        for tl_id, tl_info in tls_data.items():
            if tl_id in processed_tls:
                continue
                
            # Find neighboring TLS within coordination distance
            neighbors = self._find_coordination_neighbors(tl_id, tl_info, tls_data)
            
            if neighbors:
                group_id = f"wave_group_{len(coordination_groups) + 1}"
                coordination_groups[group_id] = [tl_id] + neighbors
                processed_tls.update([tl_id] + neighbors)
        
        return coordination_groups
    
    def _find_coordination_neighbors(self, source_tl_id: str, source_tl_info: Dict, 
                                   all_tls: Dict) -> List[str]:
        """
        Find neighboring traffic lights suitable for green wave coordination
        """
        neighbors = []
        source_pos = source_tl_info.get('position', (0, 0))
        
        for tl_id, tl_info in all_tls.items():
            if tl_id == source_tl_id:
                continue
                
            # Check distance
            tl_pos = tl_info.get('position', (0, 0))
            distance = self._calculate_distance(source_pos, tl_pos)
            
            if distance <= self.max_wave_distance:
                # Check if they're on the same arterial road
                if self._are_on_same_arterial(source_tl_info, tl_info):
                    neighbors.append(tl_id)
        
        return neighbors
    
    def _calculate_distance(self, pos1: tuple, pos2: tuple) -> float:
        """Calculate Euclidean distance between two positions"""
        return ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)**0.5
    
    def _are_on_same_arterial(self, tl1_info: Dict, tl2_info: Dict) -> bool:
        """
        Check if two traffic lights are on the same arterial road
        Based on road names, types, or connectivity patterns
        """
        tl1_roads = tl1_info.get('connected_roads', [])
        tl2_roads = tl2_info.get('connected_roads', [])
        
        # Check for common arterial road names/patterns
        arterial_indicators = ['highway', 'main', 'primary', 'secondary', 'arterial']
        
        for road1 in tl1_roads:
            for road2 in tl2_roads:
                # If they share a common road or are on connected arterials
                if road1 == road2:
                    return True
                
                # Check if both are arterial roads
                road1_lower = road1.lower()
                road2_lower = road2.lower()
                
                if any(indicator in road1_lower for indicator in arterial_indicators) and \
                   any(indicator in road2_lower for indicator in arterial_indicators):
                    return True
        
        return False
    
    def _analyze_group_wave_potential(self, group_tls: List[str], tls_data: Dict) -> Dict[str, Any]:
        """
        Analyze if a group of TLS can form an effective green wave
        """
        if len(group_tls) < 2:
            return {'feasible': False, 'reason': 'Insufficient TLS in group'}
        
        # Analyze vehicle distribution and phase alignment
        vehicle_counts = {}
        current_phases = {}
        waiting_times = {}
        
        for tl_id in group_tls:
            tl_info = tls_data.get(tl_id, {})
            performance = tl_info.get('performance', {})
            
            vehicle_counts[tl_id] = performance.get('waiting_vehicles', 0)
            current_phases[tl_id] = tl_info.get('phase_name', 'UNKNOWN')
            waiting_times[tl_id] = performance.get('avg_waiting_time', 0)
        
        # Check green wave feasibility conditions
        feasibility_check = self._check_wave_feasibility(group_tls, vehicle_counts, current_phases)
        
        if not feasibility_check['feasible']:
            return feasibility_check
        
        # Calculate expected benefit
        expected_benefit = self._calculate_expected_benefit(vehicle_counts, waiting_times)
        
        return {
            'feasible': True,
            'group_tls': group_tls,
            'direction': feasibility_check['direction'],
            'expected_benefit': expected_benefit,
            'vehicle_distribution': vehicle_counts,
            'current_phases': current_phases
        }
    
    def _check_wave_feasibility(self, group_tls: List[str], vehicle_counts: Dict, 
                              current_phases: Dict) -> Dict[str, Any]:
        """
        Check if green wave is feasible for the given group
        """
        # Condition 1: At least one TLS has significant vehicle queue
        max_vehicles = max(vehicle_counts.values())
        if max_vehicles < self.min_vehicle_count:
            return {'feasible': False, 'reason': 'Insufficient vehicles'}
        
        # Condition 2: Downstream TLS should have fewer vehicles or be empty
        viable_directions = []
        
        # Try different wave directions through the group
        for i in range(len(group_tls)):
            # Check if this direction creates a viable wave
            is_viable = True
            total_benefit = 0
            
            for j in range(i, len(group_tls)):
                current_tl = group_tls[j]
                next_tl = group_tls[j + 1] if j + 1 < len(group_tls) else None
                
                if next_tl:
                    # Downstream TLS should have fewer vehicles
                    if vehicle_counts[current_tl] > 0 and vehicle_counts[next_tl] == 0:
                        total_benefit += vehicle_counts[current_tl]
                    elif vehicle_counts[current_tl] > vehicle_counts[next_tl]:
                        total_benefit += (vehicle_counts[current_tl] - vehicle_counts[next_tl])
                    else:
                        is_viable = False
                        break
            
            if is_viable and total_benefit > 0:
                direction = f"{group_tls[i]}->{group_tls[-1]}"
                viable_directions.append({
                    'direction': direction,
                    'benefit': total_benefit,
                    'start_index': i
                })
        
        if not viable_directions:
            return {'feasible': False, 'reason': 'No viable wave direction found'}
        
        # Choose the direction with maximum benefit
        best_direction = max(viable_directions, key=lambda x: x['benefit'])
        
        return {
            'feasible': True,
            'direction': best_direction['direction'],
            'benefit_score': best_direction['benefit'],
            'start_tl': group_tls[best_direction['start_index']]
        }
    
    def _calculate_expected_benefit(self, vehicle_counts: Dict, waiting_times: Dict) -> float:
        """
        Calculate expected benefit from implementing green wave
        """
        total_vehicles = sum(vehicle_counts.values())
        avg_waiting_time = sum(waiting_times.values()) / len(waiting_times) if waiting_times else 0
        
        # Benefit formula: vehicles cleared × time saved
        expected_cleared = sum(count for count in vehicle_counts.values() if count > 0)
        time_saving_per_vehicle = 15  # Estimated seconds saved per vehicle
        
        return expected_cleared * time_saving_per_vehicle
    
    def generate_green_wave_decision(self, tls_snapshot: Dict, wave_opportunity: Dict) -> Dict[str, Any]:
        """
        Generate coordinated green wave decisions for a group of TLS
        """
        group_tls = wave_opportunity['group_tls']
        direction = wave_opportunity['direction']
        
        coordinated_decisions = []
        
        # Create phased green wave decisions
        for i, tl_id in enumerate(group_tls):
            tl_data = tls_snapshot['traffic_lights'].get(tl_id, {})
            
            # Determine appropriate action for this TLS in the wave
            wave_action = self._determine_wave_action(tl_id, tl_data, i, len(group_tls), wave_opportunity)
            
            decision = {
                'traffic_light_id': tl_id,
                'action': wave_action['type'],
                'parameters': wave_action['parameters'],
                'wave_position': i,
                'wave_direction': direction,
                'expected_impact': wave_action['impact'],
                'timestamp': time.time()
            }
            
            coordinated_decisions.append(decision)
        
        return {
            'wave_id': f"green_wave_{int(time.time())}",
            'direction': direction,
            'coordinated_decisions': coordinated_decisions,
            'total_expected_benefit': wave_opportunity['expected_benefit'],
            'group_size': len(group_tls),
            'timestamp': time.time()
        }
    
    def _determine_wave_action(self, tl_id: str, tl_data: Dict, position: int, 
                             total_tls: int, wave_opportunity: Dict) -> Dict[str, Any]:
        """
        Determine the specific action for a TLS in the green wave
        """
        vehicle_count = tl_data.get('performance', {}).get('waiting_vehicles', 0)
        current_phase = tl_data.get('phase_name', '')
        
        # First TLS in wave: extend green to clear queue
        if position == 0:
            return {
                'type': 'EXTEND_GREEN_WAVE',
                'parameters': {
                    'duration_increase': 20,  # Extended green for wave start
                    'wave_priority': 'HIGH'
                },
                'impact': 'Clear initial queue for wave propagation',
                'description': 'Extended green phase to initiate green wave'
            }
        
        # Middle TLS: synchronize with wave timing
        elif position < total_tls - 1:
            # Calculate timing offset based on position
            time_offset = position * 8  # 8 seconds between consecutive TLS
            
            return {
                'type': 'SYNCHRONIZE_GREEN',
                'parameters': {
                    'time_offset': time_offset,
                    'duration': 15,
                    'coordinate_with_previous': True
                },
                'impact': 'Maintain wave synchronization',
                'description': 'Synchronized green phase for wave continuity'
            }
        
        # Last TLS in wave: prepare for wave arrival
        else:
            if vehicle_count == 0:  # Empty junction - perfect for wave
                return {
                    'type': 'PREPARE_GREEN_WAVE',
                    'parameters': {
                        'early_green': True,
                        'duration': 12
                    },
                    'impact': 'Ready to receive wave traffic',
                    'description': 'Prepare green phase for arriving wave traffic'
                }
            else:  # Has some vehicles but fewer than upstream
                return {
                    'type': 'OPTIMIZE_FOR_WAVE',
                    'parameters': {
                        'clearance_time': 10,
                        'wave_priority': 'MEDIUM'
                    },
                    'impact': 'Balance local traffic with wave needs',
                    'description': 'Optimize phase for wave integration'
                }
    
    def should_activate_green_wave(self, tls_snapshot: Dict, current_time: float) -> bool:
        """
        Determine if conditions are favorable for green wave activation
        """
        analysis = self.analyze_network_conditions(tls_snapshot)
        
        if not analysis['green_wave_opportunities']:
            return False
        
        # Check if any opportunity has significant benefit
        best_opportunity = max(analysis['green_wave_opportunities'], 
                             key=lambda x: x['expected_benefit'], default=None)
        
        if not best_opportunity:
            return False
        
        # Minimum benefit threshold
        min_benefit = 50  # Arbitrary units - adjust based on calibration
        return best_opportunity['expected_benefit'] >= min_benefit
    
    def integrate_with_ai_decision(self, tls_snapshot: Dict, current_time: float) -> Dict[str, Any]:
        """
        Integrate green wave analysis with main AI decision making
        """
        # First, check if green wave should be activated
        if self.should_activate_green_wave(tls_snapshot, current_time):
            analysis = self.analyze_network_conditions(tls_snapshot)
            best_opportunity = max(analysis['green_wave_opportunities'], 
                                 key=lambda x: x['expected_benefit'])
            
            # Generate green wave decisions
            wave_decision = self.generate_green_wave_decision(tls_snapshot, best_opportunity)
            
            return {
                'primary_strategy': 'GREEN_WAVE',
                'wave_decision': wave_decision,
                'analysis': analysis,
                'timestamp': current_time
            }
        
        else:
            # Fall back to normal AI optimization
            return {
                'primary_strategy': 'STANDARD_AI',
                'wave_decision': None,
                'analysis': {'green_wave_opportunities': []},
                'timestamp': current_time
            }

# Global instance
green_wave_service = GreenWaveService()