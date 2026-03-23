import os
import subprocess
import random

def generate_network(output_dir="net"):
    os.makedirs(output_dir, exist_ok=True)
    net_file = os.path.join(output_dir, "grid.net.xml")

    # We use netgenerate to build a simple grid network
    # For example, a 5x5 grid with 100m distance between junctions to make routes highly dense
    cmd = [
        "netgenerate",
        "--grid",
        "--grid.number", "5",
        "--grid.length", "100",
        "--output-file", net_file,
        "--no-turnarounds", "true"
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Network generated at {net_file}")
    return net_file

def generate_routes(net_file, output_dir="net", num_vehicles=100, end_time=1000, random_seed=True):
    os.makedirs(output_dir, exist_ok=True)
    route_file = os.path.join(output_dir, "routes.rou.xml")

    # Use randomTrips.py from SUMO tools to generate random routes
    # We need to find the SUMO_HOME directory to locate randomTrips.py
    # If SUMO_HOME is not set, we can try to find it from the system install
    sumo_home = os.environ.get("SUMO_HOME", "/usr/share/sumo")
    random_trips_script = os.path.join(sumo_home, "tools", "randomTrips.py")

    if not os.path.exists(random_trips_script):
        raise FileNotFoundError(f"Could not find randomTrips.py at {random_trips_script}. Is SUMO installed and SUMO_HOME set?")

    cmd = [
        "python3", random_trips_script,
        "-n", net_file,
        "-r", route_file,
        "-e", str(end_time),
        "-p", str(end_time / num_vehicles) # Period to achieve num_vehicles by end_time
    ]

    if random_seed:
        # Inject true randomness by passing a random seed to the generator.
        # This ensures the traffic patterns change on EVERY run of the presentation,
        # which means the final privacy metric percentages will dynamically fluctuate!
        cmd.extend(["--seed", str(random.randint(1, 99999))])

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Routes generated at {route_file}")
    return route_file

def generate_gui_settings(output_dir="net", settings_name="gui-settings.xml"):
    """
    Creates the visual configuration for the SUMO-GUI.
    We exaggerate vehicle sizes so their privacy state colors (Green/Yellow/Red)
    are immediately obvious to the audience during a live presentation.
    We also enable POI text visibility to display our custom on-screen display (OSD) labels.
    """
    os.makedirs(output_dir, exist_ok=True)
    settings_file = os.path.join(output_dir, settings_name)

    # <viewport zoom="150" x="250" y="250"/> ensures the camera is perfectly centered on our 5x5 map when the simulation starts.
    # <pois ... /> enables the display of our custom Scenario Name, Reasoning, and Legend text boxes.
    # Note: poiType_show must be 1 to show the 'type' field which we use for our long text strings.
    # Text size is reduced from 100 to 24 to ensure it actually fits on smaller laptop screens without clipping.
    settings_content = """<?xml version="1.0" encoding="UTF-8"?>
<viewsettings>
    <viewport zoom="150" x="250" y="250"/>
    <scheme name="real world"/>
    <vehicles vehicleName_show="0" vehicle_exaggeration="6.0" vehicleQuality="3" vehicle_minSize="15.0"/>
    <pois poiText_show="1" poiTextSize="24" poiName_show="1" poiNameSize="24" poiType_show="1" poiTypeSize="24"/>
</viewsettings>
"""
    with open(settings_file, "w") as f:
        f.write(settings_content)

    print(f"GUI settings generated at {settings_file}")
    return settings_file

def generate_sumo_config(net_file, route_file, gui_settings_file, output_dir="net", config_name="sim.sumocfg", random_seed=True):
    os.makedirs(output_dir, exist_ok=True)
    config_file = os.path.join(output_dir, config_name)

    # Extract just the filenames for the config if they are in the same dir
    net_name = os.path.basename(net_file)
    route_name = os.path.basename(route_file)
    settings_name = os.path.basename(gui_settings_file)

    # Insert random physics flag if requested
    # <seed value="<random_int>"/> tells the SUMO physics engine to use true randomness.
    # Note: SUMO requires 'seed' to be an integer, not the string 'random'.
    random_block = f'        <seed value="{random.randint(1, 99999)}"/>' if random_seed else ''

    config_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{net_name}"/>
        <route-files value="{route_name}"/>
    </input>
    <gui_only>
        <gui-settings-file value="{settings_name}"/>
    </gui_only>
    <time>
        <begin value="0"/>
        <end value="1000"/>
    </time>
    <processing>
        <time-to-teleport value="-1"/>
{random_block}
    </processing>
</configuration>
"""
    with open(config_file, "w") as f:
        f.write(config_content)

    print(f"SUMO config generated at {config_file}")
    return config_file

if __name__ == "__main__":
    net = generate_network()
    rou = generate_routes(net)
    gui = generate_gui_settings()
    generate_sumo_config(net, rou, gui)
