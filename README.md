# SUMO/TraCI Privacy Mitigation Simulation

This project is a traffic simulation built to demonstrate **privacy vulnerabilities** and **mitigation strategies** in connected vehicles.

Connected vehicles continuously share safety-related information (Basic Safety Messages or BSMs) such as location, speed, and direction. Unauthorized entities can passively collect these broadcast messages and link them over time using spatial-temporal heuristics to track vehicle movements, reveal travel patterns, and profile users.

This simulation evaluates the effectiveness of different **pseudonym change** mechanisms at the vehicle level to mitigate unauthorized tracking without relying on heavy cryptography or roadside infrastructure.

## Project Architecture

1.  **Simulator:** SUMO (Simulation of Urban MObility) simulates a dense 5x5 urban grid.
2.  **Controller:** Python via TraCI controls the simulation step-by-step, managing BSM broadcasts and pseudonym swaps.
3.  **Attacker:** A background Python class (`Attacker`) passively collects BSMs and attempts to stitch together vehicle trajectories using a predictive physics model ($Distance \le Speed \times 1.5 + 10.0$).
4.  **Dashboard:** An interactive Streamlit dashboard visualizes the mitigation performance (Linkability & Tracking Success Rate) and maps the attacker's reconstructed trajectories against ground truth.

---

## The Four Mitigation Scenarios

The simulation evaluates four distinct scenarios, progressively implementing smarter privacy defenses:

1.  **Baseline (No Privacy):** Vehicles broadcast their BSMs using a static identifier for their entire trip. The attacker can trivially track 100% of vehicles.
2.  **Naive (Blind Swaps):** Vehicles blindly change their pseudonym every 3 seconds. The attacker can easily link the new pseudonym to the old one because the vehicle's location and speed barely change in a fraction of a second.
3.  **Smart (Density + Silence):** Vehicles only change pseudonyms when near at least 2 other vehicles (Mix-Zone), and implement a short period of **Radio Silence** (disabling BSM broadcasts) for a random duration (3-6s) to break the attacker's continuity.
4.  **Hybrid (Cooperative + Adaptive Silence):** Vehicles form cooperative groups with nearby vehicles and swap pseudonyms *synchronously*. Furthermore, the duration of their Radio Silence is dynamically adapted based on their current velocity (faster vehicles require less silence to escape the attacker's search radius).

---

## Visual Interpretation (SUMO-GUI)

When running the simulation with the `--gui` flag, you can watch the mitigations occur in real-time. Look for the following color codes on the vehicles:

*   🟢 **Green (Default):** The vehicle is broadcasting normally. In the Baseline scenario, all vehicles remain green.
*   🟡 **Yellow (Pending Swap):** The vehicle is attempting to swap its pseudonym but is waiting for a dense "Mix-Zone" or a cooperative group to form.
*   🔴 **Red (Radio Silence):** The vehicle has successfully swapped its pseudonym and has temporarily **disabled its BSM broadcasts** to evade the attacker's tracking radius.

A large **On-Screen Display (OSD)** will appear overlaid on the map during the presentation. This OSD dynamically updates to show the audience the current Scenario Name, a "Logic" prompt justifying the privacy behavior, and a color legend.

> **💡 Note on Metric Fluctuation:** By default, the simulation uses true randomness. Every time you run the script, SUMO generates completely new traffic routes, spawning times, and vehicle interactions. Therefore, your final privacy metrics (Tracking Success Rate %) will dynamically fluctuate on every execution, proving to your audience that the math is being calculated in real-time rather than reading hardcoded values!

---

## How to Run

### 1. Requirements

Ensure you have SUMO installed on your system.
*   **Ubuntu/Debian:** `sudo apt-get install sumo sumo-tools sumo-doc`
*   **Mac:** `brew install sumo`

Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 2. Run the Simulation

Execute `runner.py` to generate the network, run all 4 scenarios sequentially, calculate the privacy metrics, and save the results for the dashboard.

To run with the visual presentation mode (recommended):
```bash
python3 runner.py --gui
```

*(Optional)* To see the attacker's real-time heuristic logs flooding the terminal, append the `--verbose` flag.
*(Optional)* If you need fully reproducible and static metrics (for example, to take consistent screenshots), append the `--static` flag to disable true randomness.

### 3. View the Results Dashboard

After the simulation completes, start the Streamlit application to explore the interactive charts and trajectory maps:

```bash
streamlit run dashboard.py
```
This will open a local web server (usually at `http://localhost:8501`) displaying the architectural diagrams, metric drops, and an interactive map showing how well the attacker reconstructed a specific vehicle's path.
