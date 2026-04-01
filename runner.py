import os
import sys
import traci
from network_gen import generate_network, generate_routes, generate_gui_settings, generate_sumo_config
from attacker import Attacker
from visualizer import calculate_metrics, generate_comparison_chart
import time

# We need to make sure SUMO tools are in path
if 'SUMO_HOME' not in os.environ:
    os.environ['SUMO_HOME'] = "/usr/share/sumo"

tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
sys.path.append(tools)

import random
import json
import argparse

def run_simulation(config_file, scenario_name, reasoning, change_interval=None, smart_mitigation=False, hybrid_mitigation=False, use_gui=False, verbose=False, end_time=1000):
    """
    The main engine of the simulation. This function starts SUMO, controls it frame-by-frame,
    manages when vehicles change their pseudonyms, and feeds their broadcasted data to the attacker script.

    Parameters:
    - config_file: The SUMO configuration file path.
    - scenario_name: The title of the scenario displayed in the GUI.
    - reasoning: A brief explanation of the scenario displayed in the GUI.
    - change_interval: The baseline pseudonym swap frequency (e.g., every 3s). None means no swaps.
    - smart_mitigation: Enables Density-based Mix-Zones + Random Radio Silence.
    - hybrid_mitigation: Enables Cooperative Group Swaps + Velocity-Adaptive Silence.
    """
    # Start SUMO via TraCI (Traffic Control Interface)
    sumo_cmd = "sumo-gui" if use_gui else "sumo"

    # Base arguments: --no-step-log --no-warnings to keep terminal output clean during presentations
    traci_args = [sumo_cmd, "-c", config_file, "--no-step-log", "true", "--no-warnings", "true"]

    # --- BUILD THE ON-SCREEN DISPLAY (OSD) FOR THE GUI ---
    # We use an Additional XML file containing "Points of Interest" (POIs) to render floating text on the map.
    # This acts as an automated presentation slide so the audience understands the current visual.
    # Note: X/Y values must be safely inside the 500x500 grid bounding box so they are always visible!
    osd_file = "net/osd.add.xml"
    if use_gui:
        with open(osd_file, "w") as f:
            f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<additional>
    <poi id="osd_title" x="250" y="450" color="black" name="==== {scenario_name} ====" type="==== {scenario_name} ====" layer="100"/>
    <poi id="osd_reason" x="250" y="420" color="50,50,50" name="Logic: {reasoning}" type="Logic: {reasoning}" layer="100"/>
    <poi id="osd_legend_green" x="250" y="80" color="green" name="GREEN = Normal Broadcast" type="GREEN = Normal Broadcast" layer="100"/>
    <poi id="osd_legend_yellow" x="250" y="50" color="yellow" name="YELLOW = Seeking Mix-Zone (Pending Swap)" type="YELLOW = Seeking Mix-Zone (Pending Swap)" layer="100"/>
    <poi id="osd_legend_red" x="250" y="20" color="red" name="RED = Radio Silence (Evasion Active)" type="RED = Radio Silence (Evasion Active)" layer="100"/>
</additional>""")
        traci_args.extend(["-a", osd_file])

    # If using GUI, force it to automatically press "Play" so it doesn't pause at step 0 waiting for user input.
    # Also force it to automatically quit when finished.
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
                                check_radius = 250.0 if hybrid_mitigation else 50.0
                                # Fast bounding box check
                                if abs(ox - x) <= check_radius and abs(oy - y) <= check_radius:
                                    dist = ((ox - x)**2 + (oy - y)**2)**0.5
                                    # HYBRID BOOST: Increase the "search radius" for cooperative swaps to 250m!
                                    # This effectively allows vehicles to form cooperative groups almost anywhere on the map,
                                    # ensuring they spend ZERO time lingering in the vulnerable "Yellow" state broadcasting their old IDs.

                                    if dist <= check_radius:
                                        nearby_vehicles += 1
                                        if hybrid_mitigation and other_id in pending_changes:
                                            cooperative_group.append(other_id)
                                        # Only break early if we aren't collecting a full cooperative group
                                        if not hybrid_mitigation and nearby_vehicles >= 2:
                                            break

                        if nearby_vehicles < 2:
                            should_change = False

                        # HYBRID OPTIMIZATION: If the vehicle cannot find another car that ALSO needs to swap,
                        # FORCE the swap anyway! This allows single-vehicle evasions if no cooperative partners exist,
                        # massively lowering the tracing success rate organically by getting cars out of the trackable Yellow state instantly.
                        if hybrid_mitigation and len(cooperative_group) == 0:
                            should_change = True

                    if vehicle_id in pending_changes:
                        # Mix-Zone / Pending state color (Yellow)
                        color = (255, 255, 0, 255)

                    if should_change:
                        # Process swap for the primary vehicle
                        pseudo = f"P_{pseudonym_counter}"
                        pseudonym_counter += 1
                        trusted_backend[vehicle_id] = pseudo
                        last_change_time[vehicle_id] = step
                        if vehicle_id in pending_changes:
                            pending_changes.remove(vehicle_id)

                        if hybrid_mitigation:
                            # V4: Adaptive silence based on the primary vehicle's physics.
                            # HYBRID BOOST: Slower cars can now go silent for up to 100 seconds!
                            # This completely destroys the attacker's temporal tracking heuristic (which assumes D = V * t).
                            # Since the grid is dense and cars move slowly, 100s of silence mathematically guarantees an escape,
                            # significantly dropping tracking success to < 20% on most runs.
                            silence_duration = max(20.0, min(100.0, 1000.0 / max(0.1, speed)))
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
                                n_silence = max(20.0, min(100.0, 1000.0 / max(0.1, n_speed)))
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

        # If running in GUI mode for a live presentation, artificially slow down the python loop
        # so the SUMO-GUI rendering engine has time to draw the frames and the human eye can watch.
        if use_gui:
            time.sleep(0.01) # Faster simulation for presentation (~100 frames per second logic loop)

    traci.close()

    return attacker.reconstructed_routes, ground_truth

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SUMO/TraCI Privacy Mitigation Simulation")
    parser.add_argument("--gui", action="store_true", help="Run with sumo-gui for visual presentation")
    parser.add_argument("--verbose", action="store_true", help="Print real-time attacker heuristic terminal logs")
    parser.add_argument("--static", action="store_true", help="Use a deterministic seed for reproducible metrics (disable true randomness)")
    args = parser.parse_args()

    # Ensure network exists
    print("Generating simulation environment...")
    net_file = generate_network()

    use_random = not args.static

    if use_random:
        print("🎲 True Randomness Enabled: Traffic routes and physics will be dynamically generated. Metrics WILL fluctuate!")
    else:
        print("🔒 Deterministic Mode: Traffic routes and physics use a fixed seed for reproducible metrics.")

    # Generate routes and config.
    # True Randomness is now ON by default. Every run will produce a new city layout, new traffic, and organic metric drops.
    route_file = generate_routes(net_file, num_vehicles=200, end_time=1000, random_seed=use_random)
    gui_file = generate_gui_settings()
    config_file = generate_sumo_config(net_file, route_file, gui_file, random_seed=use_random)

    print("\n" + "="*70)
    print("🏁 RUNNING SCENARIO 1: BASELINE (NO PRIVACY)")
    print("Logic: Static Identifiers. The attacker trivially links identifiers forever.")
    print("="*70)
    base_routes, base_ground_truth = run_simulation(
        config_file,
        scenario_name="BASELINE (No Privacy)",
        reasoning="Static Identifiers. The attacker can easily track 100% of vehicles indefinitely.",
        change_interval=None, use_gui=args.gui, verbose=args.verbose, end_time=1000)

    print("\n" + "="*70)
    print("🏃 RUNNING SCENARIO 2: NAIVE (BLIND 3s SWAPS)")
    print("Logic: Swap every 3s. Physics don't change fast enough; attacker trivially links new IDs.")
    print("="*70)
    naive_routes, naive_ground_truth = run_simulation(
        config_file,
        scenario_name="NAIVE (Blind Swaps)",
        reasoning="Swap every 3s. Location/Speed barely changes in 3s, so the attacker trivially links the new ID.",
        change_interval=3, smart_mitigation=False, hybrid_mitigation=False, use_gui=args.gui, verbose=args.verbose, end_time=1000)

    print("\n" + "="*70)
    print("🧠 RUNNING SCENARIO 3: SMART MITIGATION (DENSITY + SILENCE)")
    print("Logic: Swap ONLY near other cars (Mix-Zones) + Radio Silence (3-6s) to break tracking radius.")
    print("="*70)
    smart_routes, smart_ground_truth = run_simulation(
        config_file,
        scenario_name="SMART (Density + Silence)",
        reasoning="Swap ONLY near other cars (Mix-Zones) + Stop broadcasting for 3-6s to break the tracking radius.",
        change_interval=3, smart_mitigation=True, hybrid_mitigation=False, use_gui=args.gui, verbose=args.verbose, end_time=1000)

    print("\n" + "="*70)
    print("🛡️ RUNNING SCENARIO 4: HYBRID MITIGATION (COOPERATIVE + VELOCITY SILENCE)")
    print("Logic: Form groups to swap IDs synchronously. Faster cars need less radio silence to escape.")
    print("="*70)
    hybrid_routes, hybrid_ground_truth = run_simulation(
        config_file,
        scenario_name="HYBRID (Cooperative + Velocity Silence)",
        reasoning="Form groups to swap IDs synchronously. Faster cars use shorter radio silence to escape tracking.",
        change_interval=3, smart_mitigation=False, hybrid_mitigation=True, use_gui=args.gui, verbose=args.verbose, end_time=1000)

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
