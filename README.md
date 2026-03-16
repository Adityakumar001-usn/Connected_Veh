# Connected Vehicle Privacy Simulation (SUMO & TraCI)

This project provides a comprehensive, empirically-driven Python simulation to demonstrate privacy vulnerabilities in Connected Vehicles (CVs) and evaluate the effectiveness of decentralized, lightweight pseudonym-change mitigation strategies.

Connected vehicles continuously share safety-related information (location, speed, heading) via Basic Safety Messages (BSMs). Without robust privacy measures, unauthorized entities can passively collect these broadcasts and link them over time using spatial-temporal heuristics to track vehicle movements, reveal travel patterns, and profile users.

This simulation models a passive tracking attacker and pits them against four progressively sophisticated defense architectures.

## Technology Stack

*   **Simulator:** Eclipse SUMO (Simulation of Urban MObility)
*   **Interface:** TraCI (Traffic Control Interface) library
*   **Language:** Python 3.12+
*   **Data Analysis & Visualization:** Matplotlib, Numpy, Streamlit

---

## The Four Progressive Scenarios

The simulation evaluates four distinct scenarios to demonstrate how tracking heuristics can be broken.

### 1. V1 - Baseline (No Mitigations)
Vehicles use static identifiers (their original SUMO IDs) for the duration of their trip. They continuously broadcast BSMs with their real identities, making it trivial for an observer to track their full spatial-temporal path.
*   **Result**: ~100% Tracking Success, 100% Linkability.

### 2. V2 - Naive Approach (Blind Time-Swaps)
Vehicles blindly swap their pseudonyms at a fixed time interval (e.g., every 3 seconds), regardless of their surroundings. Because the vehicle is easily visible before and after the swap, the attacker can seamlessly link the new pseudonym to the old one based on trajectory continuation.
*   **Result**: ~77% Tracking Success, ~97% Linkability.

### 3. V3 - Smart Mitigation (Density + Random Silence)
Introduces a **Vehicle-Level Mix Zone**. A vehicle only changes its ID if it detects at least 2 other vehicles within a 50-meter radius (acting as cover). Once triggered, it undergoes a **Radio Silence Period**, stopping BSM broadcasts for a random 3 to 6 seconds while moving, thoroughly breaking the attacker's trajectory tracking.
*   **Result**: ~82% Tracking Success, 0% Linkability (The Digital Identity Chain is broken).

### 4. V4 - Hybrid Mitigation (Cooperative Handshake + Adaptive Silence)
Introduces the **Cooperative Handshake** and **Adaptive Silence**. If a vehicle meets the density threshold, it checks if any neighbors *also* need a swap. They then perform the pseudonym swap simultaneously at the exact same simulation step. Additionally, the silence duration dynamically adjusts to physics: `max(3.0, min(10.0, 100.0 / max(0.1, n_speed)))` (faster vehicles stay silent for less time).
*   **Result**: ~75% Tracking Success, 0% Linkability (Physical tracking degraded by 25%).

---

## Project Architecture & Modules

The simulation is split into modular Python scripts to keep the logic lightweight, transparent, and portable.

### 1. `network_gen.py` (Dynamic Map Generation)
Programmatically generates the SUMO simulation environment to ensure reproducibility. It executes `netgenerate` to create a highly dense 5x5 grid network with 100m segment lengths, which naturally forces the vehicle interactions necessary to test density-based privacy mitigations effectively. It then uses SUMO's `randomTrips.py` to populate the grid with 200 vehicles and automatically constructs the `sim.sumocfg` file.

### 2. `attacker.py` (The Passive Observer Logic)
Models an unauthorized observer attempting to track vehicles. It passively collects BSMs (pseudonym, x, y, speed, angle, timestamp) every step. It maintains active tracks and uses a **spatial-temporal heuristic**: If a track ends (a pseudonym disappears) and a new one starts (a new pseudonym appears) within a plausible `speed * delta_t` spatial distance in the subsequent frame, the attacker assumes they are the same vehicle and links them together.

### 3. `runner.py` (The Main TraCI Loop)
The core execution script that coordinates the simulation. It launches TraCI, loops through the four simulation scenarios, and manages the "Trusted Backend System" mapping of True IDs to temporary Pseudonyms.

**Core Responsibilities:**
*   Evaluates the $O(N^2)$ density checks (optimized with a fast bounding-box spatial check before calculating exact Euclidean distances to prevent TraCI timeouts).
*   Executes the pseudonym swaps.
*   Manages the silence periods (preventing the BSM from being passed to the `attacker.py` instance).
*   Saves final simulation metrics to `results/metrics.json` for external visualization.

### 4. `visualizer.py` (Metrics Engine)
Calculates the final mathematical evaluation metrics based on the attacker's reconstructed tracks versus the ground truth:
*   **Tracking Success Rate**: The percentage of a vehicle's total physical route length that the attacker successfully reconstructed in a single, unbroken track.
*   **Linkability**: The percentage of successful pseudonym swaps the attacker guessed correctly.

### 5. `dashboard.py` (Interactive Streamlit Presentation)
A standalone presentation dashboard built with Streamlit. It reads `results/metrics.json` dynamically to generate a highly visual, interactive web application. The dashboard lays out the problem, compares the four progressive strategies side-by-side with pseudo-code snippets, visually highlights the massive drop in linkability via a 4-way grouped Matplotlib bar chart, and provides a final engineering takeaway.

---

## Installation & Execution

### Prerequisites
1.  **SUMO**: The Eclipse SUMO traffic simulator must be installed on your system.
    ```bash
    sudo apt-get update
    sudo apt-get install -y sumo sumo-tools sumo-doc
    ```
2.  **SUMO_HOME Variable**: Ensure the `SUMO_HOME` environment variable is set (default on Ubuntu is usually `/usr/share/sumo`). The `runner.py` script attempts to export this automatically if missing.

### Python Environment Setup
Install the required Python packages (TraCI, Pandas, Matplotlib, Streamlit):
```bash
pip install -r requirements.txt
```

### Running the Simulation
To execute the four scenarios sequentially and generate the metrics data:
```bash
python runner.py
```
*Note: This will automatically build the `net/` directory and save output logs to `results/metrics.json`.*

### Viewing the Dashboard
To launch the interactive presentation dashboard to visualize the results:
```bash
streamlit run dashboard.py
```
Navigate to `http://localhost:8501` in your web browser.
