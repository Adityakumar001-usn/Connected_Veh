import os
import subprocess
import random

def generate_network(output_dir="net"):
    os.makedirs(output_dir, exist_ok=True)
    net_file = os.path.join(output_dir, "grid.net.xml")

    # We use netgenerate to build a simple grid network
    # For example, a 5x5 grid with 200m distance between junctions
    cmd = [
        "netgenerate",
        "--grid",
        "--grid.number", "5",
        "--grid.length", "200",
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

def generate_sumo_config(net_file, route_file, output_dir="net", config_name="sim.sumocfg"):
    os.makedirs(output_dir, exist_ok=True)
    config_file = os.path.join(output_dir, config_name)

    # Extract just the filenames for the config if they are in the same dir
    net_name = os.path.basename(net_file)
    route_name = os.path.basename(route_file)

    config_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{net_name}"/>
        <route-files value="{route_name}"/>
    </input>
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
    generate_sumo_config(net, rou)
