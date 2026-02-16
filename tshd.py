"""
Trailing Suction Hopper Dredger (TSHD) Entity
Represents a dredger with its workflow states
"""
import json
import time
import numpy as np
from enum import Enum
from dataclasses import dataclass
from des_framework import Event, EventType, Simulation
from segments import SegmentManager


# #region agent log
_DEBUG_LOG_PATH = r"d:\###Onedrive\OneDrive\#Github\#Cursor\1\.cursor\debug.log"


def _debug_log(*, runId: str, hypothesisId: str, location: str, message: str, data: dict):
    try:
        payload = {
            "id": f"log_{int(time.time() * 1000)}_{hypothesisId}",
            "timestamp": int(time.time() * 1000),
            "runId": runId,
            "hypothesisId": hypothesisId,
            "location": location,
            "message": message,
            "data": data,
        }
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass


# #endregion agent log


class TSHDState(Enum):
    """States of the TSHD"""
    IDLE = "idle"
    DREDGING = "dredging"
    MOVING_TO_DA = "moving_to_da"
    DUMPING = "dumping"
    MOVING_BACK = "moving_back"


@dataclass
class TSHDConfig:
    """Configuration parameters for TSHD"""
    dredging_time: float = 2.0  # hours to fill hopper (mean)
    dredging_stdev_pct: float = 10.0  # percentage standard deviation for dredging time
    speed_to_da: float = 10.0  # knots
    distance_to_da: float = 5.0  # nautical miles
    moving_stdev_pct: float = 15.0  # percentage standard deviation for moving operations
    dumping_time: float = 0.5  # hours to dump material (mean)
    dumping_stdev_pct: float = 10.0  # percentage standard deviation for dumping time
    speed_back: float = 10.0  # knots
    distance_back: float = 5.0  # nautical miles
    hopper_capacity: float = 5000.0  # cubic meters


class TSHD:
    """Trailing Suction Hopper Dredger entity"""
    
    def __init__(self, entity_id: str, config: TSHDConfig = None):
        self.entity_id = entity_id
        self.config = config or TSHDConfig()
        self.state = TSHDState.IDLE
        self.hopper_level = 0.0  # Current material in hopper (cubic meters)
        self.total_dredged = 0.0  # Total material dredged
        self.cycle_count = 0
        self.event_log = []  # Store events for visualization
        self.state_history = []  # Store state changes over time
        self._debug_logged_once = {
            "dredging": False,
            "moving_to_da": False,
            "dumping": False,
            "moving_back": False,
        }
        self.current_segment_index = None
        
    def handle_event(self, event: Event, sim: Simulation):
        """Handle events for this TSHD"""
        if event.event_type == EventType.DREDGING_START:
            self._start_dredging(event, sim)
        elif event.event_type == EventType.DREDGING_COMPLETE:
            self._complete_dredging(event, sim)
        elif event.event_type == EventType.MOVE_TO_DA_START:
            self._start_move_to_da(event, sim)
        elif event.event_type == EventType.MOVE_TO_DA_COMPLETE:
            self._complete_move_to_da(event, sim)
        elif event.event_type == EventType.DUMPING_START:
            self._start_dumping(event, sim)
        elif event.event_type == EventType.DUMPING_COMPLETE:
            self._complete_dumping(event, sim)
        elif event.event_type == EventType.MOVE_BACK_START:
            self._start_move_back(event, sim)
        elif event.event_type == EventType.MOVE_BACK_COMPLETE:
            self._complete_move_back(event, sim)
    
    def _start_dredging(self, event: Event, sim: Simulation):
        """Start dredging operation"""
        self.state = TSHDState.DREDGING
        self.event_log.append({
            'time': sim.clock,
            'event': 'Starting dredging',
            'state': self.state.value
        })
        self.state_history.append({'time': sim.clock, 'state': self.state.value})
        
        # If segmentation is enabled, allocate volume from next segment
        allocated_volume_m3 = self.config.hopper_capacity
        distance_to_da_nm = self.config.distance_to_da
        seg_idx = None

        seg_mgr = getattr(sim, "segment_manager", None)
        if isinstance(seg_mgr, SegmentManager):
            alloc = seg_mgr.allocate(self.config.hopper_capacity)
            if alloc is None or alloc.volume_m3 <= 0:
                # No work left
                self.state = TSHDState.IDLE
                self.event_log.append(
                    {
                        "time": sim.clock,
                        "event": "No segment work remaining (idle)",
                        "state": self.state.value,
                    }
                )
                return

            seg_idx = alloc.segment_index
            self.current_segment_index = seg_idx
            allocated_volume_m3 = alloc.volume_m3
            distance_to_da_nm = alloc.distance_to_da_nm

        # Calculate stochastic dredging time using normal distribution (scale by partial load)
        mean_time = self.config.dredging_time * (allocated_volume_m3 / self.config.hopper_capacity)
        stdev = mean_time * (self.config.dredging_stdev_pct / 100.0)
        actual_dredging_time = max(0.1, np.random.normal(mean_time, stdev))  # Ensure non-negative

        # Record sampled duration for PDF plots
        self.event_log.append(
            {
                "time": sim.clock,
                "task": "dredging",
                "duration_h": actual_dredging_time,
                "volume_m3": allocated_volume_m3,
                "segment": seg_idx,
                "state": self.state.value,
            }
        )

        # #region agent log
        if not self._debug_logged_once["dredging"]:
            self._debug_logged_once["dredging"] = True
            _debug_log(
                runId=str(getattr(sim, "run_id", "run")),
                hypothesisId="H1",
                location="tshd.py:_start_dredging",
                message="Sampled dredging duration",
                data={
                    "entity": self.entity_id,
                    "mean_h": mean_time,
                    "stdev_pct": self.config.dredging_stdev_pct,
                    "stdev_h": stdev,
                    "sample_h": actual_dredging_time,
                },
            )
        # #endregion agent log
        
        # Schedule completion event
        completion_time = sim.clock + actual_dredging_time
        sim.schedule_event(Event(
            time=completion_time,
            event_type=EventType.DREDGING_COMPLETE,
            entity_id=self.entity_id,
            data={
                'actual_dredging_time': actual_dredging_time,
                'allocated_volume_m3': allocated_volume_m3,
                'distance_to_da_nm': distance_to_da_nm,
                'segment_index': seg_idx,
            }
        ))
    
    def _complete_dredging(self, event: Event, sim: Simulation):
        """Complete dredging and start moving to dumping area"""
        loaded_m3 = float(event.data.get("allocated_volume_m3", self.config.hopper_capacity))
        self.hopper_level = loaded_m3
        self.total_dredged += loaded_m3
        
        # Get actual dredging time from event data if available
        actual_dredging_time = event.data.get('actual_dredging_time', self.config.dredging_time)
        sim.statistics['total_dredging_time'] += actual_dredging_time
        
        self.event_log.append({
            'time': sim.clock,
            'event': f'Dredging complete (hopper: {self.hopper_level:.0f} m³)',
            'state': self.state.value
        })
        
        # Start moving to dumping area
        self.state = TSHDState.MOVING_TO_DA
        
        # Distance to DA may vary by segment if segmentation is enabled
        distance_to_da_nm = float(event.data.get("distance_to_da_nm", self.config.distance_to_da))

        # Calculate stochastic travel time using normal distribution
        mean_travel_time = distance_to_da_nm / self.config.speed_to_da
        stdev = mean_travel_time * (self.config.moving_stdev_pct / 100.0)
        travel_time = max(0.01, np.random.normal(mean_travel_time, stdev))  # Ensure non-negative

        # Record sampled duration for PDF plots
        self.event_log.append(
            {
                "time": sim.clock,
                "task": "moving_to_da",
                "duration_h": travel_time,
                "distance_nm": distance_to_da_nm,
                "segment": event.data.get("segment_index"),
                "state": self.state.value,
            }
        )

        # #region agent log
        if not self._debug_logged_once["moving_to_da"]:
            self._debug_logged_once["moving_to_da"] = True
            _debug_log(
                runId=str(getattr(sim, "run_id", "run")),
                hypothesisId="H2",
                location="tshd.py:_complete_dredging",
                message="Sampled move-to-DA duration",
                data={
                    "entity": self.entity_id,
                    "mean_h": mean_travel_time,
                    "stdev_pct": self.config.moving_stdev_pct,
                    "stdev_h": stdev,
                    "sample_h": travel_time,
                },
            )
        # #endregion agent log
        
        sim.schedule_event(Event(
            time=sim.clock,
            event_type=EventType.MOVE_TO_DA_START,
            entity_id=self.entity_id
        ))
        
        sim.schedule_event(Event(
            time=sim.clock + travel_time,
            event_type=EventType.MOVE_TO_DA_COMPLETE,
            entity_id=self.entity_id,
            data={'actual_travel_time': travel_time, 'distance_to_da_nm': distance_to_da_nm}
        ))
    
    def _start_move_to_da(self, event: Event, sim: Simulation):
        """Start moving to dumping area"""
        self.state = TSHDState.MOVING_TO_DA
        self.event_log.append({
            'time': sim.clock,
            'event': 'Moving to dumping area',
            'state': self.state.value
        })
        self.state_history.append({'time': sim.clock, 'state': self.state.value})
    
    def _complete_move_to_da(self, event: Event, sim: Simulation):
        """Arrive at dumping area and start dumping"""
        # Get actual travel time from event data if available
        distance_to_da_nm = float(event.data.get("distance_to_da_nm", self.config.distance_to_da))
        travel_time = event.data.get('actual_travel_time', distance_to_da_nm / self.config.speed_to_da)
        sim.statistics['total_moving_time'] += travel_time
        
        self.event_log.append({
            'time': sim.clock,
            'event': 'Arrived at dumping area',
            'state': self.state.value
        })
        
        # Start dumping
        self.state = TSHDState.DUMPING
        self.state_history.append({'time': sim.clock, 'state': self.state.value})
        
        # Calculate stochastic dumping time using normal distribution
        mean_time = self.config.dumping_time
        stdev = mean_time * (self.config.dumping_stdev_pct / 100.0)
        actual_dumping_time = max(0.05, np.random.normal(mean_time, stdev))  # Ensure non-negative

        # Record sampled duration for PDF plots
        self.event_log.append(
            {
                "time": sim.clock,
                "task": "dumping",
                "duration_h": actual_dumping_time,
                "state": self.state.value,
            }
        )

        # #region agent log
        if not self._debug_logged_once["dumping"]:
            self._debug_logged_once["dumping"] = True
            _debug_log(
                runId=str(getattr(sim, "run_id", "run")),
                hypothesisId="H3",
                location="tshd.py:_complete_move_to_da",
                message="Sampled dumping duration",
                data={
                    "entity": self.entity_id,
                    "mean_h": mean_time,
                    "stdev_pct": self.config.dumping_stdev_pct,
                    "stdev_h": stdev,
                    "sample_h": actual_dumping_time,
                },
            )
        # #endregion agent log
        
        sim.schedule_event(Event(
            time=sim.clock,
            event_type=EventType.DUMPING_START,
            entity_id=self.entity_id
        ))
        
        sim.schedule_event(Event(
            time=sim.clock + actual_dumping_time,
            event_type=EventType.DUMPING_COMPLETE,
            entity_id=self.entity_id,
            data={'actual_dumping_time': actual_dumping_time}
        ))
    
    def _start_dumping(self, event: Event, sim: Simulation):
        """Start dumping operation"""
        self.state = TSHDState.DUMPING
        self.event_log.append({
            'time': sim.clock,
            'event': 'Starting dumping',
            'state': self.state.value
        })
    
    def _complete_dumping(self, event: Event, sim: Simulation):
        """Complete dumping and start moving back"""
        self.hopper_level = 0.0
        
        # Get actual dumping time from event data if available
        actual_dumping_time = event.data.get('actual_dumping_time', self.config.dumping_time)
        sim.statistics['total_dumping_time'] += actual_dumping_time
        self.cycle_count += 1
        sim.statistics['dredging_cycles'] += 1
        
        self.event_log.append({
            'time': sim.clock,
            'event': f'Dumping complete (cycle {self.cycle_count} finished)',
            'state': self.state.value
        })
        
        # Start moving back to dredging area
        self.state = TSHDState.MOVING_BACK
        self.state_history.append({'time': sim.clock, 'state': self.state.value})
        
        # Calculate stochastic travel time using normal distribution
        # If segmentation enabled, return distance equals distance-to-DA for that segment
        distance_to_da_nm = float(event.data.get("distance_to_da_nm", self.config.distance_back))
        mean_travel_time = distance_to_da_nm / self.config.speed_back
        stdev = mean_travel_time * (self.config.moving_stdev_pct / 100.0)
        travel_time = max(0.01, np.random.normal(mean_travel_time, stdev))  # Ensure non-negative

        # Record sampled duration for PDF plots
        self.event_log.append(
            {
                "time": sim.clock,
                "task": "moving_back",
                "duration_h": travel_time,
                "distance_nm": distance_to_da_nm,
                "state": self.state.value,
            }
        )

        # #region agent log
        if not self._debug_logged_once["moving_back"]:
            self._debug_logged_once["moving_back"] = True
            _debug_log(
                runId=str(getattr(sim, "run_id", "run")),
                hypothesisId="H4",
                location="tshd.py:_complete_dumping",
                message="Sampled move-back duration",
                data={
                    "entity": self.entity_id,
                    "mean_h": mean_travel_time,
                    "stdev_pct": self.config.moving_stdev_pct,
                    "stdev_h": stdev,
                    "sample_h": travel_time,
                },
            )
        # #endregion agent log
        
        sim.schedule_event(Event(
            time=sim.clock,
            event_type=EventType.MOVE_BACK_START,
            entity_id=self.entity_id
        ))
        
        sim.schedule_event(Event(
            time=sim.clock + travel_time,
            event_type=EventType.MOVE_BACK_COMPLETE,
            entity_id=self.entity_id,
            data={'actual_travel_time': travel_time, 'distance_to_da_nm': distance_to_da_nm}
        ))
    
    def _start_move_back(self, event: Event, sim: Simulation):
        """Start moving back to dredging area"""
        self.state = TSHDState.MOVING_BACK
        self.event_log.append({
            'time': sim.clock,
            'event': 'Moving back to dredging area',
            'state': self.state.value
        })
    
    def _complete_move_back(self, event: Event, sim: Simulation):
        """Arrive back at dredging area and start next cycle"""
        # Get actual travel time from event data if available
        travel_time = event.data.get('actual_travel_time', self.config.distance_back / self.config.speed_back)
        sim.statistics['total_moving_time'] += travel_time
        
        self.event_log.append({
            'time': sim.clock,
            'event': 'Arrived back at dredging area',
            'state': self.state.value
        })
        
        # Start next dredging cycle
        self.state = TSHDState.DREDGING
        self.state_history.append({'time': sim.clock, 'state': self.state.value})
        sim.schedule_event(Event(
            time=sim.clock,
            event_type=EventType.DREDGING_START,
            entity_id=self.entity_id
        ))
    
    def start_work(self, sim: Simulation):
        """Initialize the TSHD to start working"""
        sim.schedule_event(Event(
            time=0.0,
            event_type=EventType.DREDGING_START,
            entity_id=self.entity_id
        ))
