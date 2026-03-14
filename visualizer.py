import os
import matplotlib.pyplot as plt

def calculate_metrics(attacker_routes, ground_truth):
    """
    Calculates Linkability and Tracking Success Rate.

    attacker_routes: dict of track_id -> [bsm1, bsm2, ...]
    ground_truth: list of dicts: {'true_id': ..., 'pseudonym': ..., 'timestamp': ...}
                  or similar structure to map BSM to true vehicle.
    """
    # Convert ground truth to a more accessible format
    # Let's organize ground truth by true_id to know the full route of each vehicle
    true_routes = {}

    # We also need a fast lookup for a specific (pseudonym, timestamp) -> true_id
    pseudo_time_to_true_id = {}

    # Track pseudonym swaps
    # true_id -> list of pseudonyms used in order
    vehicle_pseudonyms = {}

    for entry in ground_truth:
        true_id = entry['true_id']
        pseudo = entry['pseudonym']
        ts = entry['timestamp']

        if true_id not in true_routes:
            true_routes[true_id] = []
            vehicle_pseudonyms[true_id] = []

        true_routes[true_id].append(entry)
        pseudo_time_to_true_id[(pseudo, ts)] = true_id

        if len(vehicle_pseudonyms[true_id]) == 0 or vehicle_pseudonyms[true_id][-1] != pseudo:
            vehicle_pseudonyms[true_id].append(pseudo)

    # --- Metric 1: Tracking Success Rate ---
    # Percentage of a vehicle's total route that the attacker successfully reconstructs.
    # For a given true_id, we find which track_id covers the most steps of its route.
    # Then success rate = max_steps_in_one_track / total_steps

    tracking_success_rates = []

    for true_id, route in true_routes.items():
        total_steps = len(route)
        if total_steps == 0:
            continue

    # Build the reverse map from attacker_routes
    attacker_lookup = {}
    for track_id, bsms in attacker_routes.items():
        for bsm in bsms:
            attacker_lookup[(bsm['pseudonym'], bsm['timestamp'])] = track_id

    for true_id, route in true_routes.items():
        total_steps = len(route)
        if total_steps == 0:
            continue

        track_counts = {}
        for entry in route:
            pseudo = entry['pseudonym']
            ts = entry['timestamp']

            track_id = attacker_lookup.get((pseudo, ts))
            if track_id is not None:
                track_counts[track_id] = track_counts.get(track_id, 0) + 1

        if track_counts:
            max_tracked_steps = max(track_counts.values())
        else:
            max_tracked_steps = 0

        success_rate = (max_tracked_steps / total_steps) * 100
        tracking_success_rates.append(success_rate)

    avg_tracking_success = sum(tracking_success_rates) / len(tracking_success_rates) if tracking_success_rates else 0

    # --- Metric 2: Linkability ---
    # Percentage of successful pseudonym swaps the attacker guesses correctly.
    # If a vehicle changes pseudonym 5 times, and attacker links old & new ID 2 times -> 40%.

    total_swaps = 0
    successful_links = 0

    for true_id, pseudonyms in vehicle_pseudonyms.items():
        num_swaps = len(pseudonyms) - 1
        if num_swaps <= 0:
            continue

        total_swaps += num_swaps

        # Check each swap
        for i in range(num_swaps):
            old_pseudo = pseudonyms[i]
            new_pseudo = pseudonyms[i+1]

            # A swap is successfully linked if the attacker placed the last BSM of old_pseudo
            # and the first BSM of new_pseudo in the SAME track_id

            # Find the last timestamp of old_pseudo
            last_old_entry = next((e for e in reversed(true_routes[true_id]) if e['pseudonym'] == old_pseudo), None)
            first_new_entry = next((e for e in true_routes[true_id] if e['pseudonym'] == new_pseudo), None)

            if last_old_entry and first_new_entry:
                old_track_id = attacker_lookup.get((old_pseudo, last_old_entry['timestamp']))
                new_track_id = attacker_lookup.get((new_pseudo, first_new_entry['timestamp']))

                if old_track_id is not None and old_track_id == new_track_id:
                    successful_links += 1

    linkability = (successful_links / total_swaps * 100) if total_swaps > 0 else 100.0
    # Note: if there are no swaps (baseline), linkability is technically 100% since everything is linked perfectly

    return {
        "Tracking Success Rate (%)": avg_tracking_success,
        "Linkability (%)": linkability
    }

def generate_comparison_chart(baseline_metrics, mitigated_metrics, output_dir="results"):
    os.makedirs(output_dir, exist_ok=True)

    # Prepare data
    labels = list(baseline_metrics.keys())
    baseline_values = [baseline_metrics[l] for l in labels]
    mitigated_values = [mitigated_metrics[l] for l in labels]

    x = range(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 6))

    bars1 = ax.bar([p - width/2 for p in x], baseline_values, width, label='Baseline', color='#ff9999')
    bars2 = ax.bar([p + width/2 for p in x], mitigated_values, width, label='Smart Mitigation', color='#66b3ff')

    ax.set_ylabel('Percentage (%)')
    ax.set_title('Privacy Metrics Comparison: Baseline vs Smart Mitigation')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 110)
    ax.legend()

    # Add values on top of bars
    for bar in bars1 + bars2:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')

    plt.tight_layout()

    output_path = os.path.join(output_dir, "privacy_metrics_comparison.png")
    plt.savefig(output_path, dpi=300)
    print(f"Comparison chart saved to {output_path}")

    return output_path
