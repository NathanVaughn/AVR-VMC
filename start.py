#!/usr/bin/python3

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import warnings
from typing import Any, List, Literal

# vendor PyYAML so we don't need to pip install anything
from resources.pyyaml.lib import yaml
from utils import check_sudo

# for docker compose. Modern versisons of Docker only accept lower case
DOCKER_PROJECT_NAME = "avr"
ACTION_CHOCIES = Literal["run", "build", "pull", "stop"]

IMAGE_BASE = "ghcr.io/bellflight/avr/"
THIS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
MODULES_DIR = os.path.join(THIS_DIR, "modules")

# Environment variable constants

# MQTT broker settings
MQTT_HOST = "mqtt"
MQTT_PORT = 18830

# PX4 flight controller serial device settings
FCC_SERIAL_DEVICE = "/dev/ttyTHS1"
FCC_SERIAL_BAUD_RATE = 500000

# Mavlink connection settings
MAVLINK_TCP_1 = 5760  # for QGC
MAVLINK_UDP_1 = 14541  # for mavsdk
MAVLINK_UDP_2 = 14542  # for pymavlink

# Peripheral control computer (Arduino) device settings
PCC_SERIAL_DEVICE = "/dev/ttyACM0"
PCC_SERIAL_BAUD_RATE = 115200

# PX4 Origin settings
PX4_HOME_LAT = 32.808549
PX4_HOME_LON = -97.156345
PX4_HOME_ALT = 161.5


def get_ip_address() -> str:
    # https://stackoverflow.com/a/30990617/9944427
    # network access not actually required, but we need to pick a valid ip address
    # that is routed externally
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("1.1.1.1", 80))
    name = s.getsockname()[0]
    s.close()
    return name


def apriltag_service(compose_services: dict, action: ACTION_CHOCIES) -> None:
    apriltag_dir = os.path.join(MODULES_DIR, "apriltag")

    argus_socket = "/tmp/argus_socket"
    nvidia_lib_dir = "/opt/nvidia/vpi1/"

    apriltag_data = {
        "depends_on": ["mqtt"],
        "build": apriltag_dir,
        "restart": "on-failure",
        "environment": {"MQTT_HOST": MQTT_HOST, "MQTT_PORT": MQTT_PORT},
        "volumes": [f"{argus_socket}:{argus_socket}"],
    }

    # cannot run if the argus socket does not exist
    if not os.path.isfile(argus_socket) and action == "run":
        warnings.warn(
            f"Argus socket {argus_socket} does not exist, cannot run Apriltag, skipping"
        )
        return

    # cannot build without nvidia libraries
    if not os.path.isdir(nvidia_lib_dir) and action == "build":
        warnings.warn("Nvidia libraries do not exist, cannot build Apriltag, skipping")
        return

    compose_services["apriltag"] = apriltag_data


def fcm_service(compose_services: dict, local: bool = False) -> None:
    fcm_dir = os.path.join(MODULES_DIR, "fcm")

    fcm_data = {
        "depends_on": ["mqtt", "mavp2p"],
        "restart": "on-failure",
        "environment": {"MQTT_HOST": MQTT_HOST, "MQTT_PORT": MQTT_PORT},
    }

    if local:
        fcm_data["build"] = fcm_dir
    else:
        fcm_data["image"] = f"{IMAGE_BASE}flightcontrol:latest"

    compose_services["fcm"] = fcm_data


def fusion_service(compose_services: dict, local: bool = False) -> None:
    fusion_dir = os.path.join(MODULES_DIR, "fusion")

    fusion_data = {
        "depends_on": ["mqtt", "vio"],
        "restart": "on-failure",
        "environment": {
            "MQTT_HOST": MQTT_HOST,
            "MQTT_PORT": MQTT_PORT,
            "PX4_HOME_LAT": PX4_HOME_LAT,
            "PX4_HOME_LON": PX4_HOME_LON,
            "PX4_HOME_ALT": PX4_HOME_ALT,
        },
    }

    if local:
        fusion_data["build"] = fusion_dir
    else:
        fusion_data["image"] = f"{IMAGE_BASE}fusion:latest"

    compose_services["fusion"] = fusion_data


def mavp2p_service(
    compose_services: dict,
    action: ACTION_CHOCIES,
    local: bool = False,
    simulator: bool = False,
) -> None:
    mavp2p_data = {
        "restart": "on-failure",
        "ports": [f"{MAVLINK_TCP_1}:{MAVLINK_TCP_1}/tcp"],
        "command": " ".join(
            [
                f"tcps:0.0.0.0:{MAVLINK_TCP_1}",
                f"udpc:fcm:{MAVLINK_UDP_1}",
                f"udpc:fcm:{MAVLINK_UDP_2}",
            ]
        ),
        "environment": {"MAVLINK_UDP_1": MAVLINK_UDP_1, "MAVLINK_UDP_2": MAVLINK_UDP_2},
    }

    if simulator:
        # when using simulator, allow connection from the offboard mavlink port
        mavp2p_data["command"] += " udps:0.0.0.0:14540"
        mavp2p_data["ports"] += ["14540:14540/udp"]

    if not simulator:
        # when not in simulator, add fcc serial device
        mavp2p_data["command"] = (
            f"serial:{FCC_SERIAL_DEVICE}:{FCC_SERIAL_BAUD_RATE} "
            + mavp2p_data["command"]
        )
        mavp2p_data["devices"] = [f"{FCC_SERIAL_DEVICE}:{FCC_SERIAL_DEVICE}"]

        # cannot run without FCC plugged in
        if not os.path.exists(FCC_SERIAL_DEVICE) and action == "run":
            warnings.warn(
                f"FCC serial device {FCC_SERIAL_DEVICE} does not exist, cannot run mavp2p, skipping"
            )
            return

    if local:
        mavp2p_data["build"] = os.path.join(MODULES_DIR, "mavp2p")
    else:
        mavp2p_data["image"] = f"{IMAGE_BASE}mavp2p:latest"

    compose_services["mavp2p"] = mavp2p_data


def mqtt_service(compose_services: dict, local: bool = False) -> None:
    mqtt_data = {
        "ports": [f"{MQTT_PORT}:{MQTT_PORT}/tcp"],
        "environment": {"MQTT_PORT": MQTT_PORT},
        "restart": "on-failure",
    }

    if local:
        mqtt_data["build"] = os.path.join(MODULES_DIR, "mqtt")
    else:
        mqtt_data["image"] = f"{IMAGE_BASE}mosquitto:latest"

    compose_services["mqtt"] = mqtt_data


def pcm_service(
    compose_services: dict, action: ACTION_CHOCIES, local: bool = False
) -> None:
    pcm_dir = os.path.join(MODULES_DIR, "pcm")

    pcm_data = {
        "depends_on": ["mqtt"],
        "restart": "on-failure",
        "devices": [f"{PCC_SERIAL_DEVICE}:{PCC_SERIAL_DEVICE}"],
        "environment": {
            "MQTT_HOST": MQTT_HOST,
            "MQTT_PORT": MQTT_PORT,
            "PCC_SERIAL_DEVICE": PCC_SERIAL_DEVICE,
            "PCC_SERIAL_BAUD_RATE": PCC_SERIAL_BAUD_RATE,
        },
    }

    # cannot run without PCC plugged in
    if not os.path.exists(PCC_SERIAL_DEVICE) and action == "run":
        warnings.warn(
            f"PCC serial device {PCC_SERIAL_DEVICE} does not exist, cannot run pcm, skipping"
        )
        return

    if local:
        pcm_data["build"] = pcm_dir
    else:
        pcm_data["image"] = f"{IMAGE_BASE}peripheralcontrol:latest"

    compose_services["pcm"] = pcm_data


def sandbox_service(compose_services: dict) -> None:
    sandbox_dir = os.path.join(MODULES_DIR, "sandbox")

    sandbox_data = {
        "depends_on": ["mqtt"],
        "build": sandbox_dir,
        "restart": "on-failure",
        "environment": {"MQTT_HOST": MQTT_HOST, "MQTT_PORT": MQTT_PORT},
    }

    # cannot build or run without files (duh)
    if not os.path.isdir(sandbox_dir):
        warnings.warn("Sandbox directory does not exist, skipping")
        return

    compose_services["sandbox"] = sandbox_data


def simulator_service(compose_services: dict, local: bool = False) -> None:
    simulator_dir = os.path.join(MODULES_DIR, "simulator")

    if os.name != "posix":
        print(
            "Sorry, the simulator can only be launched from WSL or Linux due to"
            + " environment variables and volumes."
        )
        sys.exit(1)

    # https://stackoverflow.com/a/73901260/9944427
    # https://github.com/microsoft/wslg/blob/main/samples/container/Containers.md

    simulator_data = {
        "tty": True,
        "stdin_open": True,
        "environment": {
            "DISPLAY": os.environ["DISPLAY"],
            "WAYLAND_DISPLAY": os.environ["WAYLAND_DISPLAY"],
            "XDG_RUNTIME_DIR": os.environ["XDG_RUNTIME_DIR"],
            "PULSE_SERVER": os.environ["PULSE_SERVER"],
            "PX4_HOME_LAT": PX4_HOME_LAT,
            "PX4_HOME_LON": PX4_HOME_LON,
            "PX4_HOME_ALT": PX4_HOME_ALT,
            "DOCKER_HOST": get_ip_address(),
        },
        "volumes": ["/tmp/.X11-unix:/tmp/.X11-unix", "/mnt/wslg:/mnt/wslg"],
    }

    if local:
        simulator_data["build"] = simulator_dir
    else:
        simulator_data["image"] = f"{IMAGE_BASE}simulator:latest"

    compose_services["simulator"] = simulator_data


# def simulator_service(
#     compose_services: dict, action: ACTION_CHOCIES, local: bool = False
# ) -> None:
#     simulator_dir = os.path.join(MODULES_DIR, "simulator")

#     # https://stackoverflow.com/a/73901260/9944427
#     # https://github.com/microsoft/wslg/blob/main/samples/container/Containers.md

#     simulator_data = {}

#     if local:
#         image = f"{DOCKER_PROJECT_NAME}-simulator:latest"
#         simulator_data["build"] = simulator_dir
#     else:
#         image = f"{IMAGE_BASE}simulator:latest"
#         simulator_data["image"] = image

#     if action == "build":
#         compose_services["simulator"] = simulator_data

#     elif action == "run":
#         # for now, only work with Windows terminal
#         # need to run as seperate process so that we can get an interactive terminal
#         wt = "wt.exe"
#         if os.name == "posix":
#             wt = "/mnt/c/Users/nvaug/AppData/Local/Microsoft/WindowsApps/wt.exe"

#         terminal_cmd = [
#             wt,
#             "--window",
#             "new",
#             "nt",
#         ]
#         docker_cmd = [
#             "docker",
#             "run",
#             "-it",
#             "--rm",
#             # "-p",
#             # "14540:14540/udp",
#             "-v",
#             "/tmp/.X11-unix:/tmp/.X11-unix",
#             "-v",
#             "/mnt/wslg:/mnt/wslg",
#             "-e",
#             "DISPLAY",
#             "-e",
#             "WAYLAND_DISPLAY",
#             "-e",
#             "XDG_RUNTIME_DIR",
#             "-e",
#             "PULSE_SERVER",
#             "-e",
#             f"PX4_HOME_LAT={PX4_HOME_LAT}",
#             "-e",
#             f"PX4_HOME_LON={PX4_HOME_LON}",
#             "-e",
#             f"PX4_HOME_ALT={PX4_HOME_ALT}",
#             image,
#         ]

#         cmd = terminal_cmd + ["wsl"] + docker_cmd
#         # print(" ".join(cmd))
#         subprocess.Popen(cmd)


def status_service(
    compose_services: dict, action: ACTION_CHOCIES, local: bool = False
) -> None:
    # don't create a volume for nvpmodel if it's not available
    nvpmodel_source = shutil.which("nvpmodel")
    nvpmodel_conf = "/etc/nvpmodel.conf"

    status_dir = os.path.join(MODULES_DIR, "status")

    # use the older style of bind mounts for older docker-compose compatibility
    status_data = {
        "depends_on": ["mqtt"],
        "restart": "on-failure",
        "privileged": True,
        "environment": {"MQTT_HOST": MQTT_HOST, "MQTT_PORT": MQTT_PORT},
        "volumes": [
            "/etc/nvpmodel.conf:/app/nvpmodel.conf",
            f"{nvpmodel_source}:/app/nvpmodel",
        ],
    }

    # cannot run without nvpmodel or its configuration
    if (not os.path.isfile(nvpmodel_conf) or not nvpmodel_source) and action == "run":
        warnings.warn("nvpmodel could not be found, cannot run status, skipping")
        return

    if local:
        status_data["build"] = status_dir
    else:
        status_data["image"] = f"{IMAGE_BASE}status:latest"

    compose_services["status"] = status_data


def thermal_service(compose_services: dict, local: bool = False) -> None:
    thermal_dir = os.path.join(MODULES_DIR, "thermal")

    thermal_data = {
        "depends_on": ["mqtt"],
        "restart": "on-failure",
        "privileged": True,
        "environment": {"MQTT_HOST": MQTT_HOST, "MQTT_PORT": MQTT_PORT},
    }

    if local:
        thermal_data["build"] = thermal_dir
    else:
        thermal_data["image"] = f"{IMAGE_BASE}thermal:latest"

    # realistically this can't run without the thermal camera connected, but this is
    # difficult to detect without all the Adafruit libraries
    compose_services["thermal"] = thermal_data


def vio_service(compose_services: dict, local: bool = False) -> None:
    vio_dir = os.path.join(MODULES_DIR, "vio")

    vio_data = {
        "depends_on": ["mqtt"],
        "restart": "on-failure",
        "privileged": True,
        "environment": {"MQTT_HOST": MQTT_HOST, "MQTT_PORT": MQTT_PORT},
        "volumes": [f"{os.path.join(vio_dir, 'settings')}:/usr/local/zed/settings/"],
    }

    if local:
        vio_data["build"] = vio_dir
    else:
        vio_data["image"] = f"{IMAGE_BASE}visual:latest"

    # realistically this can't run without the ZED Mini connected, but also
    # hard to detect without USB shenangians
    compose_services["vio"] = vio_data


def prepare_compose_file(
    action: ACTION_CHOCIES, modules: List[str], local: bool = False
) -> str:
    simulator = "simulator" in modules

    # prepare compose services dict
    compose_services = {}

    # should always be available
    mqtt_service(compose_services, local)
    mavp2p_service(compose_services, action, local, simulator)

    if "apriltag" in modules:
        # apriltag is always built on device
        apriltag_service(compose_services, action)
    if "fcm" in modules:
        fcm_service(compose_services, local)
    if "fusion" in modules:
        fusion_service(compose_services, local)
    if "pcm" in modules:
        pcm_service(compose_services, action, local)
    if "sandbox" in modules:
        # sandbox is always built on device
        sandbox_service(compose_services)
    if "status" in modules:
        status_service(compose_services, action, local)
    if "thermal" in modules:
        thermal_service(compose_services, local)
    if "vio" in modules:
        vio_service(compose_services, local)

    if "simulator" in modules:
        simulator_service(compose_services, local)

    # construct full dict
    compose_data = {"version": "3", "services": compose_services}

    # write compose file
    compose_file = os.path.join(THIS_DIR, "docker-compose.yml")

    with open(compose_file, "w") as fp:
        yaml.dump(compose_data, fp)

    # return file path
    return compose_file


def main(action: ACTION_CHOCIES, modules: List[str], local: bool = False) -> None:
    compose_file = prepare_compose_file(action, modules=modules, local=local)

    # # as simulator runs seperate
    # # do nothing if that is the only selection
    # if modules == ["simulator"]:
    #     return

    # prefer newer docker compose if available
    docker_compose = [shutil.which("docker"), "compose"]
    if (
        subprocess.run(
            docker_compose + ["--help"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        != 0
    ):
        docker_compose = [shutil.which("docker-compose")]

    # pyright is upset because shutil.which could return None
    cmd: List[str] = docker_compose + ["--project-name", DOCKER_PROJECT_NAME, "--file", compose_file]  # type: ignore

    if action == "build":
        cmd += ["build"] + modules
    elif action == "pull":
        cmd += ["pull"] + modules
    elif action == "run":
        cmd += ["up", "--remove-orphans", "--force-recreate"] + modules
    elif action == "stop":
        cmd += ["down", "--remove-orphans", "--volumes"]
    else:
        # shouldn't happen
        raise ValueError(f"Unknown action: {action}")

    print(f"Running command: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, cwd=THIS_DIR)

    def signal_handler(sig: Any, frame: Any) -> None:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGINT)

    signal.signal(signal.SIGINT, signal_handler)
    proc.wait()

    sys.exit(proc.returncode)


# sourcery skip: merge-duplicate-blocks, remove-redundant-if
if __name__ == "__main__":
    check_sudo(__file__)

    min_modules = ["fcm", "fusion", "mavp2p", "mqtt", "vio"]
    norm_modules = min_modules + ["apriltag", "pcm", "status", "thermal"]
    all_modules = norm_modules + ["sandbox"]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help="Build containers locally rather than using pre-built ones from GitHub",
    )

    parser.add_argument(
        "action", choices=["run", "build", "pull", "stop"], help="Action to perform"
    )
    parser.add_argument(
        "modules",
        nargs="*",
        help="Explicitly list which module(s) to perform the action one",
    )

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument(
        "-m",
        "--min",
        action="store_true",
        help=f"Perform action on minimal modules ({', '.join(sorted(min_modules))}). Adds to any modules explicitly specified.",
    )
    exgroup.add_argument(
        "-n",
        "--norm",
        action="store_true",
        help=f"Perform action on normal modules ({', '.join(sorted(norm_modules))}). Adds to any modules explicitly specified. If nothing else is specified, this is the default.",
    )
    exgroup.add_argument(
        "-a",
        "--all",
        action="store_true",
        help=f"Perform action on all modules ({', '.join(sorted(all_modules))}). Adds to any modules explicitly specified.",
    )

    args = parser.parse_args()

    if args.min:
        # minimal modules selected
        args.modules += min_modules
    elif args.norm:
        # normal modules selected
        args.modules += norm_modules
    elif args.all:
        # all modules selected
        args.modules += all_modules
    elif not args.modules:
        # nothing specified, default to normal
        args.modules = norm_modules

    args.modules = list(set(args.modules))  # remove duplicates
    main(action=args.action, modules=args.modules, local=args.local)
