"""
Simulation Runner
Main script to run the dredging simulation
"""
from des_framework import Simulation
from tshd import TSHD, TSHDConfig


def run_simulation(simulation_time: float = 24.0, num_dredgers: int = 1):
    """Run the dredging simulation"""
    
    # Create simulation
    sim = Simulation()
    
    # Create TSHD(s)
    dredgers = []
    for i in range(num_dredgers):
        config = TSHDConfig(
            dredging_time=2.0,  # hours
            speed_to_da=10.0,  # knots
            distance_to_da=5.0,  # nautical miles
            dumping_time=0.5,  # hours
            speed_back=10.0,  # knots
            distance_back=5.0,  # nautical miles
            hopper_capacity=5000.0  # cubic meters
        )
        
        dredger = TSHD(f"TSHD-{i+1}", config)
        dredgers.append(dredger)
        sim.entities[dredger.entity_id] = dredger
        
        # Start the dredger working
        dredger.start_work(sim)
    
    print("=" * 60)
    print("DISCRETE EVENT SIMULATION: TSHD DREDGING OPERATION")
    print("=" * 60)
    print(f"Simulation time: {simulation_time} hours")
    print(f"Number of dredgers: {num_dredgers}")
    print("=" * 60)
    print()
    
    # Run simulation
    sim.run(end_time=simulation_time)
    
    # Print statistics
    print()
    print("=" * 60)
    print("SIMULATION STATISTICS")
    print("=" * 60)
    stats = sim.get_statistics()
    print(f"Simulation time: {stats['simulation_time']:.2f} hours")
    print(f"Total events processed: {stats['events_processed']}")
    print(f"Total dredging cycles: {stats['dredging_cycles']}")
    print(f"Total dredging time: {stats['total_dredging_time']:.2f} hours")
    print(f"Total moving time: {stats['total_moving_time']:.2f} hours")
    print(f"Total dumping time: {stats['total_dumping_time']:.2f} hours")
    print()
    
    # Print per-dredger statistics
    for dredger in dredgers:
        print(f"{dredger.entity_id}:")
        print(f"  - Cycles completed: {dredger.cycle_count}")
        print(f"  - Total material dredged: {dredger.total_dredged:.0f} m³")
        print(f"  - Current state: {dredger.state.value}")
        print(f"  - Hopper level: {dredger.hopper_level:.0f} m³")
    
    print("=" * 60)
    
    return sim


if __name__ == "__main__":
    # Run simulation for 24 hours with 1 dredger
    run_simulation(simulation_time=24.0, num_dredgers=1)
