# Connected Vehicle Privacy Simulation (SUMO & TraCI)

**A highly detailed, empirically-driven Python simulation demonstrating privacy vulnerabilities in Connected Vehicles (CVs) and evaluating decentralized, lightweight pseudonym-change mitigation strategies.**

## 1. Project Context & Problem Statement

Connected vehicles continuously share safety-critical information—such as their location, speed, and heading—via high-frequency **Basic Safety Messages (BSMs)**. While this data is essential for collision avoidance and traffic optimization, it introduces a severe privacy vulnerability.

Because BSMs are broadcast in the clear over wireless channels (like DSRC or C-V2X), unauthorized entities can passively collect these messages. Without robust privacy measures, an attacker can link consecutive messages together over time using spatial-temporal heuristics. By tracking these persistent identifiers, an attacker can reconstruct full vehicle routes, revealing travel patterns, home/work locations, and profiling users without their consent.

**The Goal:** The objective of this project is to implement a lightweight, practical, and transparent approach that demonstrates how unauthorized vehicle tracking can be mitigated using pseudonym change–based mechanisms at the vehicle level, specifically **without relying on heavy roadside infrastructure (RSUs)** or complex cryptography.

---

## 2. Technology Stack

*   **Traffic Simulator:** Eclipse SUMO (Simulation of Urban MObility)
*   **Simulation Control Interface:** TraCI (Traffic Control Interface) library
*   **Language:** Python 3.12+
*   **Data Analysis:** Pandas (optional parsing), Numpy
*   **Visualization:** Matplotlib, Streamlit (for the interactive presentation dashboard)

---

## 3. The Attacker Model (Spatial-Temporal Tracking)

The simulation pits the connected vehicles against an unauthorized, passive observer modeled in `attacker.py`.

### 3.1 The Heuristic Logic
The attacker does not have access to the "True ID" of the vehicle. Instead, it logs the BSM data (`pseudonym, x, y, speed, angle, timestamp`) every simulation step.

When a pseudonym disappears from the network (because the vehicle swapped its ID) and a new pseudonym appears in the very next time step, the attacker attempts to mathematically link them based on physics.

### 3.2 The Plausible Distance Formula
The attacker calculates the maximum plausible distance the vehicle could have traveled in that 1-second interval:
$$ D_{max} = (Speed \times 1.5) + 10.0 \text{ meters} $$
*(The $1.5$ multiplier and $+10.0m$ buffer account for sudden acceleration and measurement error).*

If the Euclidean distance between the old pseudonym's last known location and the new pseudonym's first known location is $\le D_{max}$, the attacker greedily links them together, effectively maintaining the track across the pseudonym swap.

---

## 4. The Four Progressive Scenarios

The `runner.py` script automatically evaluates four distinct scenarios to demonstrate how tracking heuristics can be broken, measuring two critical metrics:
*   **Tracking Success Rate**: The maximum percentage of a vehicle's total physical route length that the attacker successfully reconstructed in a single, unbroken track.
*   **Linkability**: The percentage of pseudonym swaps where the attacker successfully guessed the mapping between the old ID and the new ID.

### Scenario 1: Baseline (No Mitigations)
Vehicles use static identifiers (their original SUMO IDs) for the duration of their trip. They continuously broadcast BSMs with their real identities.
*   **Mechanism**: None.
*   **Empirical Result**: ~100% Tracking Success, 100% Linkability.

### Scenario 2: Naive Approach (Blind Time-Swaps)
Vehicles swap their pseudonyms at a fixed time interval (every 3 seconds), regardless of their surroundings.
*   **Mechanism**: `if current_time - last_swap_time >= 3: swap()`
*   **Empirical Result**: ~77% Tracking Success, ~97% Linkability.
*   **Insight**: Because the vehicle broadcasts immediately before and after the swap while driving in the open, the attacker can seamlessly link the new pseudonym to the old one using the spatial-temporal heuristic.

### Scenario 3: Smart Mitigation (Density + Random Silence)
Introduces a **Vehicle-Level Mix Zone**. A vehicle only changes its ID if it detects at least 2 other vehicles within a 50-meter radius (acting as physical cover). Once triggered, it undergoes a **Radio Silence Period**, stopping BSM broadcasts for a random 3 to 6 seconds while continuing to move.
*   **Mechanism**: `if nearby_vehicles >= 2: swap() and silence(random(3, 6))`
*   **Empirical Result**: ~82% Tracking Success, **0% Linkability**.
*   **Insight**: The digital identity chain is broken. Because vehicles disappear for random durations and reappear far apart, the attacker cannot reliably map the old ID to the new ID.

### Scenario 4: Hybrid Mitigation (Cooperative Handshake + Adaptive Silence)
To combat the fact that the attacker can still physically guess the trajectory based on road constraints (~82%), V4 introduces a **Cooperative Handshake**. If a vehicle meets the density threshold, it forces its neighbors to swap pseudonyms *simultaneously* at the exact same simulation step. Additionally, the silence duration dynamically adjusts to physics: faster vehicles stay silent for less time.
*   **Mechanism**:
    ```python
    silence = max(3.0, min(10.0, 100.0 / max(0.1, speed)))
    for neighbor in cooperative_group:
        neighbor.swap()
        neighbor.silence(silence)
    ```
*   **Empirical Result**: ~75% Tracking Success, 0% Linkability.
*   **Insight**: By forcing vehicles to swap and go silent as synchronized groups with dynamic durations, the attacker's physical trajectory reconstruction is heavily degraded.

---

## 5. System Architecture & Module Deep-Dive

To ensure the implementation remains lightweight, transparent, and easy to understand, the logic is split into multiple dedicated modules.

### `network_gen.py` (Dynamic Map Generation)
Programmatically generates the SUMO simulation environment to ensure zero-dependency reproducibility.
*   **Design Choice**: It executes `netgenerate` to create a highly dense **5x5 grid network with 100m segment lengths**. This tiny, dense map naturally forces the constant vehicle interactions and traffic jams necessary to test density-based privacy mitigations effectively.
*   It uses SUMO's `randomTrips.py` to populate the grid with 200 vehicles.

### `attacker.py` (Passive Observer Logic)
*   Maintains dictionaries of active tracks (`self.active_tracks`) and reconstructed routes (`self.reconstructed_routes`).
*   Implements the $O(1)$ greedy spatial-temporal distance check every simulation step.

### `runner.py` (The TraCI Execution Loop)
The core script that boots SUMO, manages the "Trusted Backend System" mapping of True IDs to Pseudonyms, and iterates through the active vehicle list via `traci.vehicle.getIDList()`.
*   **Performance Optimization**: Checking the Euclidean distance between 200 vehicles every single frame is an $O(N^2)$ operation that causes TraCI to freeze. To prevent this, `runner.py` implements a fast **bounding-box spatial check** (`abs(ox - x) <= 50.0 and abs(oy - y) <= 50.0`) before calculating the exact math `sqrt((ox-x)^2 + (oy-y)^2)`, allowing the simulation to run in seconds rather than minutes.
*   Saves the final evaluation data to `results/metrics.json`.

### `visualizer.py` (Metrics Engine)
*   **Tracking Success Algorithm**: Finds the longest single track ID reconstructed by the attacker for a specific vehicle, and divides it by the total number of steps that vehicle was actually alive in the ground truth.
*   **Linkability Algorithm**: Checks every single pseudonym swap in the ground truth. If the attacker placed the last BSM of the old pseudonym and the first BSM of the new pseudonym into the *same* track ID, the link was successful.

### `dashboard.py` (Interactive Presentation UI)
A standalone presentation dashboard built with Streamlit.
*   Reads `results/metrics.json` dynamically.
*   Presents a highly visual, 4-column layout comparing the progressive strategies alongside their Python pseudo-code.
*   Renders a 4-way grouped Matplotlib bar chart visually highlighting the massive drop in Tracking Success and Linkability.

---

## 6. Installation & Execution Guide

### Prerequisites
1.  **SUMO Simulator**: Eclipse SUMO must be installed on your system.
    ```bash
    # Ubuntu/Debian
    sudo apt-get update
    sudo apt-get install -y sumo sumo-tools sumo-doc
    ```
2.  **SUMO_HOME Variable**: Ensure the `SUMO_HOME` environment variable is set (default on Ubuntu is `/usr/share/sumo`). The `runner.py` script will attempt to set this automatically if it is missing.

### Python Setup
Install the required dependencies using the provided requirements file:
```bash
pip install -r requirements.txt
```

### Running the Pipeline
**Step 1: Generate Data & Evaluate Metrics**
Execute the runner script. This will generate the network, run all 4 TraCI simulation scenarios, feed the data to the attacker, calculate the final metrics, and output the results to a JSON file.
```bash
python runner.py
```

**Step 2: Launch the Interactive Dashboard**
Spin up the Streamlit web server to view the final presentation, metrics, and comparison charts.
```bash
streamlit run dashboard.py
```
Navigate to `http://localhost:8501` in your web browser to view the application!