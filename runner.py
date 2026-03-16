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
import json
import argparse

def run_simulation(config_file, change_interval=None, smart_mitigation=False, hybrid_mitigation=False, use_gui=False, verbose=False, end_time=1000):
    """
    Runs the SUMO simulation and feeds BSMs to the Attacker.
    change_interval: If None, baseline scenario (no pseudonym changes).
                     If an integer (e.g., 30), pseudonym changes every 30s.
    smart_mitigation: If True, uses density-based swapping and silence periods.
    hybrid_mitigation: If True, uses cooperative swapping and velocity-adaptive silence.
    """
    # Start SUMO via TraCI
    sumo_cmd = "sumo-gui" if use_gui else "sumo"

    # Base arguments: --no-step-log --no-warnings to keep output clean
    traci_args = [sumo_cmd, "-c", config_file, "--no-step-log", "true", "--no-warnings", "true"]

    # If using GUI, force it to automatically press "Play" so it doesn't pause at step 0
    # Also force it to automatically quit when finished so it doesn't wait for user to click "Yes" to close.
    if use_gui:
        traci_args.append("--start")
        traci_args.append("--quit-on-end")

    traci.start(traci_args)

    attacker = Attacker(verbose=verbose)

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
            # Default state color (Green)
            color = (0, 255, 0, 255)

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
                    cooperative_group = []

                    if smart_mitigation or hybrid_mitigation:
                        # Density-based swapping: Check if there are at least 2 OTHER vehicles within 50m
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
                                        if hybrid_mitigation and other_id in pending_changes:
                                            cooperative_group.append(other_id)
                                        # Only break early if we aren't collecting a full cooperative group
                                        if not hybrid_mitigation and nearby_vehicles >= 2:
                                            break

                        if nearby_vehicles < 2:
                            should_change = False

                        if hybrid_mitigation and len(cooperative_group) == 0:
                            # Must swap with someone who ALSO needs a swap
                            should_change = False

                    if vehicle_id in pending_changes:
                        # Mix-Zone / Pending state color (Yellow)
                        color = (255, 255, 0, 255)

                    if should_change:
                        # Process swap for the primary vehicle
                        pseudo = f"P_{pseudonym_counter}"
                        pseudonym_counter += 1
                        trusted_backend[vehicle_id] = pseudo
                        last_change_time[vehicle_id] = step
                        pending_changes.remove(vehicle_id)

                        if hybrid_mitigation:
                            # V4: Adaptive silence based on the primary vehicle's physics.
                            silence_duration = max(3.0, min(10.0, 100.0 / max(0.1, speed)))
                            # Convert to integer steps
                            silence_duration = int(silence_duration)
                            silence_periods[vehicle_id] = step + silence_duration
                        elif smart_mitigation:
                            silence_duration = random.randint(3, 6)
                            silence_periods[vehicle_id] = step + silence_duration

                        # If hybrid, also swap the neighbors synchronously
                        if hybrid_mitigation:
                            for neighbor_id in cooperative_group:
                                pseudo = f"P_{pseudonym_counter}"
                                pseudonym_counter += 1
                                trusted_backend[neighbor_id] = pseudo
                                last_change_time[neighbor_id] = step
                                if neighbor_id in pending_changes:
                                    pending_changes.remove(neighbor_id)

                                # V4 Adaptive Silence: Use the neighbor's own physics to calculate silence!
                                n_speed = traci.vehicle.getSpeed(neighbor_id)
                                n_silence = max(3.0, min(10.0, 100.0 / max(0.1, n_speed)))
                                silence_periods[neighbor_id] = step + int(n_silence)

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
            is_silent = vehicle_id in silence_periods and step < silence_periods[vehicle_id]
            if is_silent:
                # Radio Silence state color (Red)
                color = (255, 0, 0, 255)

            # Apply color to the vehicle via TraCI
            try:
                traci.vehicle.setColor(vehicle_id, color)
            except traci.exceptions.TraCIException:
                pass # Safety catch in case vehicle departed mid-step

            if not is_silent:
                attacker.process_bsm(current_pseudonym, x, y, speed, angle, step)

            # Clean up old silence period entries
            if vehicle_id in silence_periods and step >= silence_periods[vehicle_id]:
                del silence_periods[vehicle_id]

        step += 1

    traci.close()

    return attacker.reconstructed_routes, ground_truth

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SUMO/TraCI Privacy Mitigation Simulation")
    parser.add_argument("--gui", action="store_true", help="Run with sumo-gui for visual presentation")
    parser.add_argument("--verbose", action="store_true", help="Print real-time attacker heuristic terminal logs")
    args = parser.parse_args()

    # Ensure network exists
    print("Generating simulation environment...")
    net_file = generate_network()
    route_file = generate_routes(net_file, num_vehicles=200, end_time=1000)
    config_file = generate_sumo_config(net_file, route_file)

    print("\nRunning Scenario 1: Baseline (No Pseudonym Changes)...")
    base_routes, base_ground_truth = run_simulation(config_file, change_interval=None, use_gui=args.gui, verbose=args.verbose, end_time=1000)

    print("Running Scenario 2: Naive (Blind 3s Swaps)...")
    naive_routes, naive_ground_truth = run_simulation(config_file, change_interval=3, smart_mitigation=False, hybrid_mitigation=False, use_gui=args.gui, verbose=args.verbose, end_time=1000)

    print("Running Scenario 3: Smart Mitigation (Density + Random Silence)...")
    smart_routes, smart_ground_truth = run_simulation(config_file, change_interval=3, smart_mitigation=True, hybrid_mitigation=False, use_gui=args.gui, verbose=args.verbose, end_time=1000)

    print("Running Scenario 4: Hybrid Mitigation (Cooperative Swap + Adaptive Silence)...")
    hybrid_routes, hybrid_ground_truth = run_simulation(config_file, change_interval=3, smart_mitigation=False, hybrid_mitigation=True, use_gui=args.gui, verbose=args.verbose, end_time=1000)

    print("\nCalculating Metrics...")
    metrics_data = {
        "Baseline": calculate_metrics(base_routes, base_ground_truth),
        "Naive": calculate_metrics(naive_routes, naive_ground_truth),
        "Smart": calculate_metrics(smart_routes, smart_ground_truth),
        "Hybrid": calculate_metrics(hybrid_routes, hybrid_ground_truth)
    }

    for scenario, metrics in metrics_data.items():
        print(f"\n--- {scenario} Metrics ---")
        for k, v in metrics.items():
            print(f"{k}: {v:.2f}")

    # Save metrics to JSON so dashboard.py can read them dynamically
    os.makedirs("results", exist_ok=True)
    with open("results/metrics.json", "w") as f:
        json.dump(metrics_data, f, indent=4)
    print("\nMetrics saved to results/metrics.json for dashboard usage.")

    # Select a sample vehicle that lived long enough to demonstrate trajectory breaking
    # We will grab all trajectories for 'veh_0' (or the first available vehicle) across the 4 scenarios
    sample_veh = None
    for entry in base_ground_truth:
        if entry["timestamp"] > 100:
            sample_veh = entry["true_id"]
            break
    if sample_veh is None and len(base_ground_truth) > 0:
        sample_veh = base_ground_truth[0]["true_id"]

    trajectories_data = {}

    def extract_trajectory(ground_truth, reconstructed_routes, sample_vid):
        gt_path = []
        for entry in ground_truth:
            if entry["true_id"] == sample_vid:
                gt_path.append({"x": entry["x"], "y": entry["y"]})

        # Find the attacker track that covers the MOST steps of this vehicle
        best_track_id = None
        max_steps = 0
        attacker_path = []

        # Build reverse lookup to find which track IDs contain this vehicle's pseudonyms
        # Since we just want a visual, we'll pick the track that maps to its initial pseudonym
        initial_pseudo = None
        for entry in ground_truth:
            if entry["true_id"] == sample_vid:
                initial_pseudo = entry["pseudonym"]
                break

        if initial_pseudo:
            for tid, route in reconstructed_routes.items():
                if any(bsm["pseudonym"] == initial_pseudo for bsm in route):
                    best_track_id = tid
                    break

        if best_track_id and best_track_id in reconstructed_routes:
            for bsm in reconstructed_routes[best_track_id]:
                attacker_path.append({"x": bsm["x"], "y": bsm["y"]})

        return {"ground_truth": gt_path, "attacker_track": attacker_path}

    if sample_veh:
        trajectories_data["Baseline"] = extract_trajectory(base_ground_truth, base_routes, sample_veh)
        trajectories_data["Naive"] = extract_trajectory(naive_ground_truth, naive_routes, sample_veh)
        trajectories_data["Smart"] = extract_trajectory(smart_ground_truth, smart_routes, sample_veh)
        trajectories_data["Hybrid"] = extract_trajectory(hybrid_ground_truth, hybrid_routes, sample_veh)

        with open("results/trajectories.json", "w") as f:
            json.dump(trajectories_data, f, indent=4)
        print("Trajectories saved to results/trajectories.json for dashboard mapping.")

    print("Simulation complete!")
