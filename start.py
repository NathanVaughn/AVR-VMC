#!/usr/bin/python3

import argparse
import os
import shutil
import signal
import subprocess
import sys
import warnings
from typing import Any, List

import yaml

from utils import check_sudo

IMAGE_BASE = "ghcr.io/bellflight/avr/"
THIS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
MODULES_DIR = os.path.join(THIS_DIR, "modules")


def apriltag_service(compose_services: dict) -> None:
    apriltag_dir = os.path.join(MODULES_DIR, "apriltag")

    apriltag_data = {
        "depends_on": ["mqtt"],
        "build": apriltag_dir,
        "restart": "on-failure",
        "volumes": ["/tmp/argus_socket:/tmp/argus_socket"],
    }

    compose_services["apriltag"] = apriltag_data


def fcm_service(compose_services: dict, local: bool = False) -> None:
    fcm_dir = os.path.join(MODULES_DIR, "fcm")

    fcm_data = {
        "depends_on": ["mqtt", "mavp2p"],
        "restart": "on-failure",
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
    }

    if local:
        fusion_data["build"] = fusion_dir
    else:
        fusion_data["image"] = f"{IMAGE_BASE}fusion:latest"

    compose_services["fusion"] = fusion_data


def mavp2p_service(compose_services: dict, local: bool = False) -> None:
    mavp2p_data = {
        "restart": "on-failure",
        "devices": ["/dev/ttyTHS1:/dev/ttyTHS1"],
        "ports": ["5760:5760/tcp"],
        "command": "serial:/dev/ttyTHS1:500000 tcps:0.0.0.0:5760 udpc:fcm:14541 udpc:fcm:14542",
    }

    if local:
        mavp2p_data["build"] = os.path.join(MODULES_DIR, "mavp2p")
    else:
        mavp2p_data["image"] = f"{IMAGE_BASE}mavp2p:latest"

    compose_services["mavp2p"] = mavp2p_data


def mqtt_service(compose_services: dict, local: bool = False) -> None:
    mqtt_data = {
        "ports": ["18830:18830"],
        "restart": "on-failure",
    }

    if local:
        mqtt_data["build"] = os.path.join(MODULES_DIR, "mqtt")
    else:
        mqtt_data["image"] = f"{IMAGE_BASE}mosquitto:latest"

    compose_services["mqtt"] = mqtt_data


def pcm_service(compose_services: dict, local: bool = False) -> None:
    pcm_dir = os.path.join(MODULES_DIR, "pcm")

    pcm_data = {
        "depends_on": ["mqtt"],
        "restart": "on-failure",
        "devices": ["/dev/ttyACM0:/dev/ttyACM0"],
    }

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
    }

    compose_services["sandbox"] = sandbox_data


def status_service(compose_services: dict, local: bool = False) -> None:
    # don't create a volume for nvpmodel if it's not available
    nvpmodel_source = shutil.which("nvpmodel")

    status_dir = os.path.join(MODULES_DIR, "status")

    status_data = {
        "depends_on": ["mqtt"],
        "restart": "on-failure",
        "privileged": True,
        "volumes": [
            {
                "type": "bind",
                "source": "/etc/nvpmodel.conf",
                "target": "/app/nvpmodel.conf",
            },
        ],
    }

    if nvpmodel_source:
        status_data["volumes"].append(
            {
                "type": "bind",
                "source": nvpmodel_source,
                "target": "/app/nvpmodel",
            }
        )
    else:
        warnings.warn("nvpmodel is not found")

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
    }

    if local:
        thermal_data["build"] = thermal_dir
    else:
        thermal_data["image"] = f"{IMAGE_BASE}thermal:latest"

    compose_services["thermal"] = thermal_data


def vio_service(compose_services: dict, local: bool = False) -> None:
    vio_dir = os.path.join(MODULES_DIR, "vio")

    vio_data = {
        "depends_on": ["mqtt"],
        "restart": "on-failure",
        "privileged": True,
        "volumes": [f"{os.path.join(vio_dir, 'settings')}:/usr/local/zed/settings/"],
    }

    if local:
        vio_data["build"] = vio_dir
    else:
        vio_data["image"] = f"{IMAGE_BASE}visual:latest"

    compose_services["vio"] = vio_data


def prepare_compose_file(action: str, modules: List[str], local: bool = False) -> str:
    # prepare compose services dict
    compose_services = {}

    apriltag_service(compose_services)
    fcm_service(compose_services, local)
    fusion_service(compose_services, local)
    mavp2p_service(compose_services, local)
    mqtt_service(compose_services, local)
    pcm_service(compose_services, local)
    if "sandbox" in modules:
        # older versions of Docker compose don't like it if a build directory doesn't
        # exist, even though we're not asking for that service
        sandbox_service(compose_services)
    thermal_service(compose_services, local)
    vio_service(compose_services, local)

    # nvpmodel not available on Windows
    if os.name != "nt" or action == "build":
        # only allow this if we're building
        status_service(compose_services, local)

    # construct full dict
    compose_data = {"version": "3", "services": compose_services}

    # write compose file
    compose_file = os.path.join(THIS_DIR, "docker-compose.yml")

    with open(compose_file, "w") as fp:
        yaml.dump(compose_data, fp)

    # return file path
    return compose_file


def main(action: str, modules: List[str], local: bool = False) -> None:
    compose_file = prepare_compose_file(action, modules=modules, local=local)

    # run docker-compose
    project_name = "AVR"
    if os.name == "nt":
        # for some reason on Windows docker-compose doesn't like upper case???
        project_name = project_name.lower()

    cmd = ["docker-compose", "--project-name", project_name, "--file", compose_file]

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
