import os
import sys
import traci
from network_gen import generate_network, generate_routes, generate_sumo_config
from attacker import Attacker
from visualizer import calculate_metrics, generate_comparison_chart

# We need to make sure SUMO tools are in path
if 'SUMO_HOME' not in os.environ:
    os.environ['SUMO_HOME'] = "/usr/share/sumo"

tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
sys.path.append(tools)

import random

def run_simulation(config_file, change_interval=None, smart_mitigation=False, end_time=1000):
    """
    Runs the SUMO simulation and feeds BSMs to the Attacker.
    change_interval: If None, baseline scenario (no pseudonym changes).
                     If an integer (e.g., 30), pseudonym changes every 30s.
    smart_mitigation: If True, uses density-based swapping and silence periods.
    """
    # Start SUMO via TraCI
    # --no-step-log --no-warnings to keep output clean
    traci.start(["sumo", "-c", config_file, "--no-step-log", "true", "--no-warnings", "true"])

    attacker = Attacker()

    # Trusted Backend System mapping: True ID -> Current Pseudonym
    trusted_backend = {}

    # Track when the vehicle last changed its pseudonym
    last_change_time = {}

    # Track silence periods (vehicle_id -> end_step_of_silence)
    silence_periods = {}

    # Track vehicles that are waiting for density condition to change pseudonym
    pending_changes = set()

    # Running counter for generating pseudonyms
    pseudonym_counter = 1

    ground_truth = []

    step = 0
    while step < end_time:
        traci.simulationStep()

        active_vehicles = traci.vehicle.getIDList()

        for vehicle_id in active_vehicles:
            # Initialize for new vehicles
            if vehicle_id not in trusted_backend:
                pseudo = f"P_{pseudonym_counter}"
                pseudonym_counter += 1
                trusted_backend[vehicle_id] = pseudo
                last_change_time[vehicle_id] = step

            # Extract basic info first
            x, y = traci.vehicle.getPosition(vehicle_id)
            speed = traci.vehicle.getSpeed(vehicle_id)
            angle = traci.vehicle.getAngle(vehicle_id)

            # Pseudonym change logic
            if change_interval is not None:
                if step - last_change_time[vehicle_id] >= change_interval:
                    pending_changes.add(vehicle_id)

                if vehicle_id in pending_changes:
                    should_change = True
                    if smart_mitigation:
                        # Density-based swapping: Check if there are at least 2 OTHER vehicles within 100m
                        nearby_vehicles = 0

                        # Optimization: filter by bounding box first to avoid O(N^2)
                        for other_id in active_vehicles:
                            if other_id != vehicle_id:
                                ox, oy = traci.vehicle.getPosition(other_id)
                                # Fast bounding box check
                                if abs(ox - x) <= 50.0 and abs(oy - y) <= 50.0:
                                    dist = ((ox - x)**2 + (oy - y)**2)**0.5
                                    if dist <= 50.0:
                                        nearby_vehicles += 1
                                        if nearby_vehicles >= 2:
                                            break # We only need to know if there are at least 2

                        if nearby_vehicles < 2:
                            should_change = False

                    if should_change:
                        # Time to swap pseudonym
                        pseudo = f"P_{pseudonym_counter}"
                        pseudonym_counter += 1
                        trusted_backend[vehicle_id] = pseudo
                        last_change_time[vehicle_id] = step
                        pending_changes.remove(vehicle_id)

                        if smart_mitigation:
                            # Enter silence period: stop broadcasting for 3 to 6 seconds
                            silence_duration = random.randint(3, 6)
                            silence_periods[vehicle_id] = step + silence_duration

            # Get current pseudonym
            current_pseudonym = trusted_backend[vehicle_id]

            # Record Ground Truth for evaluation (always recorded, even during silence)
            ground_truth.append({
                "true_id": vehicle_id,
                "pseudonym": current_pseudonym,
                "x": x,
                "y": y,
                "speed": speed,
                "angle": angle,
                "timestamp": step
            })

            # Broadcast BSM to Attacker (Attacker ONLY sees this if not in a silence period)
            is_silent = smart_mitigation and vehicle_id in silence_periods and step < silence_periods[vehicle_id]
            if not is_silent:
                attacker.process_bsm(current_pseudonym, x, y, speed, angle, step)

            # Clean up old silence period entries
            if vehicle_id in silence_periods and step >= silence_periods[vehicle_id]:
                del silence_periods[vehicle_id]

        step += 1

    traci.close()

    return attacker.reconstructed_routes, ground_truth

if __name__ == "__main__":
    # Ensure network exists
    print("Generating simulation environment...")
    net_file = generate_network()
    route_file = generate_routes(net_file, num_vehicles=200, end_time=1000)
    config_file = generate_sumo_config(net_file, route_file)

    print("\nRunning Baseline Scenario (No Pseudonym Changes)...")
    base_routes, base_ground_truth = run_simulation(config_file, change_interval=None, end_time=1000)

    print("Running Smart Mitigation Scenario (Density + Silence)...")
    mit_routes, mit_ground_truth = run_simulation(config_file, change_interval=3, smart_mitigation=True, end_time=1000)

    print("\nCalculating Metrics...")
    # Evaluate Baseline
    baseline_metrics = calculate_metrics(base_routes, base_ground_truth)
    print("--- Baseline Metrics ---")
    for k, v in baseline_metrics.items():
        print(f"{k}: {v:.2f}")

    # Evaluate Mitigated
    mitigated_metrics = calculate_metrics(mit_routes, mit_ground_truth)
    print("\n--- Smart Mitigation Metrics ---")
    for k, v in mitigated_metrics.items():
        print(f"{k}: {v:.2f}")

    print("\nGenerating Comparison Chart...")
    generate_comparison_chart(baseline_metrics, mitigated_metrics)
    print("Simulation complete!")
