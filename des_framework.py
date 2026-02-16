"""
Discrete Event Simulation Framework
Basic framework for managing events and simulation time
"""
import heapq
from typing import Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    """Types of events in the simulation"""
    DREDGING_START = "dredging_start"
    DREDGING_COMPLETE = "dredging_complete"
    MOVE_TO_DA_START = "move_to_da_start"
    MOVE_TO_DA_COMPLETE = "move_to_da_complete"
    DUMPING_START = "dumping_start"
    DUMPING_COMPLETE = "dumping_complete"
    MOVE_BACK_START = "move_back_start"
    MOVE_BACK_COMPLETE = "move_back_complete"


@dataclass
class Event:
    """Represents a discrete event in the simulation"""
    time: float
    event_type: EventType
    entity_id: str
    data: dict = field(default_factory=dict)
    
    def __lt__(self, other):
        """For priority queue ordering by time"""
        return self.time < other.time


class Simulation:
    """Main simulation engine"""
    
    def __init__(self):
        self.clock = 0.0  # Current simulation time
        self.event_queue = []  # Priority queue of events
        self.entities = {}  # Dictionary of simulation entities
        self.statistics = {
            'total_dredging_time': 0.0,
            'total_moving_time': 0.0,
            'total_dumping_time': 0.0,
            'dredging_cycles': 0,
            'events_processed': 0
        }
        self.running = False
        
    def schedule_event(self, event: Event):
        """Schedule an event to occur at a future time"""
        heapq.heappush(self.event_queue, event)
        
    def get_next_event(self) -> Event:
        """Get and remove the next event from the queue"""
        if self.event_queue:
            return heapq.heappop(self.event_queue)
        return None
    
    def run(self, end_time: float = None):
        """Run the simulation until end_time or until no more events"""
        self.running = True
        
        while self.event_queue and self.running:
            event = self.get_next_event()
            
            if end_time and event.time > end_time:
                heapq.heappush(self.event_queue, event)  # Put it back
                self.clock = end_time
                break
                
            self.clock = event.time
            self.statistics['events_processed'] += 1
            
            # Process the event
            if event.entity_id in self.entities:
                entity = self.entities[event.entity_id]
                entity.handle_event(event, self)
            else:
                print(f"Warning: Entity {event.entity_id} not found for event {event.event_type}")
        
        self.running = False
        
    def stop(self):
        """Stop the simulation"""
        self.running = False
        
    def get_statistics(self) -> dict:
        """Get simulation statistics"""
        return {
            **self.statistics,
            'simulation_time': self.clock,
            'entities': len(self.entities)
        }
