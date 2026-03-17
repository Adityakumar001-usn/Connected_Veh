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

def generate_routes(net_file, output_dir="net", num_vehicles=100, end_time=1000):
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

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Routes generated at {route_file}")
    return route_file

def generate_gui_settings(output_dir="net", settings_name="gui-settings.xml"):
    os.makedirs(output_dir, exist_ok=True)
    settings_file = os.path.join(output_dir, settings_name)

    # Create a GUI settings file that significantly exaggerates vehicle sizes
    # so their colors (Green, Yellow, Red) are easily visible during a live presentation.
    # It also enables POI (Points of Interest) text to be visible so we can show scenario labels.
    settings_content = """<?xml version="1.0" encoding="UTF-8"?>
<viewsettings>
    <scheme name="real world"/>
    <vehicles vehicleName_show="0" vehicle_exaggeration="6.0" vehicleQuality="3" vehicle_minSize="15.0"/>
    <pois poiText_show="1" poiTextSize="100" poiName_show="1" poiNameSize="100"/>
</viewsettings>
"""
    with open(settings_file, "w") as f:
        f.write(settings_content)

    print(f"GUI settings generated at {settings_file}")
    return settings_file

def generate_sumo_config(net_file, route_file, gui_settings_file, output_dir="net", config_name="sim.sumocfg"):
    os.makedirs(output_dir, exist_ok=True)
    config_file = os.path.join(output_dir, config_name)

    # Extract just the filenames for the config if they are in the same dir
    net_name = os.path.basename(net_file)
    route_name = os.path.basename(route_file)
    settings_name = os.path.basename(gui_settings_file)

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
