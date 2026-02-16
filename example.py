"""
Example usage of the TSHD dredging simulation
Demonstrates different configurations and scenarios
"""
from simulation_runner import run_simulation
from des_framework import Simulation
from tshd import TSHD, TSHDConfig


def example_basic():
    """Basic simulation with default parameters"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Simulation")
    print("="*60 + "\n")
    run_simulation(simulation_time=24.0, num_dredgers=1)


def example_multiple_dredgers():
    """Simulation with multiple dredgers"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Multiple Dredgers")
    print("="*60 + "\n")
    run_simulation(simulation_time=24.0, num_dredgers=3)


def example_custom_config():
    """Simulation with custom TSHD configuration"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Custom Configuration")
    print("="*60 + "\n")
    
    sim = Simulation()
    
    # Create TSHD with custom parameters (larger capacity, slower speed)
    config = TSHDConfig(
        dredging_time=4.0,        # Longer dredging time
        speed_to_da=8.0,          # Slower speed
        distance_to_da=8.0,       # Further dumping area
        dumping_time=1.0,         # Longer dumping time
        speed_back=8.0,           # Slower return speed
        distance_back=8.0,        # Same distance back
        hopper_capacity=8000.0    # Larger hopper
    )
    
    dredger = TSHD("TSHD-Large", config)
    sim.entities[dredger.entity_id] = dredger
    dredger.start_work(sim)
    
    print(f"TSHD Configuration:")
    print(f"  Dredging time: {config.dredging_time} hours")
    print(f"  Speed: {config.speed_to_da} knots")
    print(f"  Distance to DA: {config.distance_to_da} nautical miles")
    print(f"  Dumping time: {config.dumping_time} hours")
    print(f"  Hopper capacity: {config.hopper_capacity} m³")
    print()
    
    sim.run(end_time=48.0)
    
    stats = sim.get_statistics()
    print()
    print(f"Statistics:")
    print(f"  Cycles completed: {stats['dredging_cycles']}")
    print(f"  Total material dredged: {dredger.total_dredged:.0f} m³")
    print(f"  Utilization: {(stats['total_dredging_time'] / stats['simulation_time'] * 100):.1f}%")


def example_extended_simulation():
    """Extended simulation over longer period"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Extended Simulation (1 week)")
    print("="*60 + "\n")
    run_simulation(simulation_time=168.0, num_dredgers=2)  # 1 week = 168 hours


if __name__ == "__main__":
    # Run all examples
    example_basic()
    example_multiple_dredgers()
    example_custom_config()
    example_extended_simulation()
