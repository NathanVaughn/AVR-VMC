#!/usr/bin/python3

import argparse
import contextlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

from utils import check_sudo

# colors
RED = "\033[0;31m"
LIGHTRED = "\033[1;31m"
GREEN = "\033[0;32m"
LIGHTGREEN = "\033[1;32m"
CYAN = "\033[0;36m"
NC = "\033[0m"  # No Color

HOME_DIR = os.path.expanduser("~")
AVR_DIR = os.path.join(HOME_DIR, "AVR-VMC")


def print_bar():
    """
    Print a bar equal to the width of the current terminal.
    """
    print("=" * os.get_terminal_size().columns)


def print_title(title):
    """
    Print a title with a bar.
    """
    print(f"{CYAN}{title}{NC}")
    print_bar()


def original_user_cmd(username, cmd):
    """
    Take a command list, and return a version that runs as the given username.
    """
    return ["sudo", "-u", username, "-i"] + cmd


def add_line_to_file(filename, line):
    """
    Add a line to the bottom of a file. Does not do anything if the line already exists.
    """
    with open(filename, "r") as fp:
        lines = fp.readlines()

    if line not in lines:
        with open(filename, "w") as fp:
            fp.writelines(lines + [line])

    return


def main(development):
    if not os.path.isdir(AVR_DIR):
        print(f"AVR repository has not been cloned to {AVR_DIR}")
        print(
            f"Do this with 'git clone --recurse-submodules https://github.com/nathanvaughn/AVR-VMC {AVR_DIR}'"
        )
        sys.exit(1)

    # fmt: off
    print(f"{RED}")
    print("██████████████████████████████████████████████████████████████████████████")
    print(f"█████████████████████████████████████████████████████████████████████{NC}TM{RED}███")
    print("████▌              ▀████            ████     ██████████     ██████████████")
    print("██████▄▄▄  ▄▄▄▄     ▐███    ▄▄▄▄▄▄▄▄████     ██████████     ██████████████")
    print("███████▀   █████    ████    ▀▀▀▀▀▀▀▀████     ██████████     ██████████████")
    print("███████            ▀████            ████     ██████████     ██████████████")
    print("███████    ▄▄▄▄▄     ███    ████████████     ██████████     ██████████████")
    print("███████    ████▀     ███    ▀▀▀▀▀▀▀▀████     ▀▀▀▀▀▀▀███     ▀▀▀▀▀▀▀▀██████")
    print("███████             ▄███            ████            ███             ██████")
    print("███████▄▄▄▄▄▄▄▄▄▄▄██████▄▄▄▄▄▄▄▄▄▄▄▄████▄▄▄▄▄▄▄▄▄▄▄▄███▄▄▄▄▄▄▄▄▄▄▄▄▄██████")
    print("██████████████████████████████████████████████████████████████████████████")
    print("                                                                          ")
    print("██████████████████████████████▄▄          ▄▄██████████████████████████████")
    print("██████████████████████████████████▄    ▄██████████████████████████████████")
    print("████████████████████████████████████  ████████████████████████████████████")
    print("███▀▀▀▀▀██████████████████████████▀    ▀██████████████████████████▀▀▀▀▀███")
    print("████▄▄          ▀▀▀▀█████████████        █████████████▀▀▀▀          ▄▄████")
    print("████████▄▄▄                ▀▀▀▀▀██████████▀▀▀▀▀                ▄▄▄████████")
    print("█████████████▄▄                   ▀████▀                   ▄▄█████████████")
    print("█████████████████▄                  ██                  ▄█████████████████")
    print("██████████████████████████████▀     ██     ▀██████████████████████████████")
    print("███████████████████████▀▀           ██           ▀▀███████████████████████")
    print("████████████████▀▀▀                 ██                 ▀▀▀████████████████")
    print("█████████▀▀                       ▄████▄                       ▀▀█████████")
    print("████▀▀                         ▄███▀  ▀███▄                         ▀▀████")
    print(" ████▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█████▀      ▀█████▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄████ ")
    print(" ▀███████████████████████████████▄      ▄███████████████████████████████▀ ")
    print("  ▀████████████████████████████████    ████████████████████████████████▀  ")
    print("    ██████████████████████████████▀    ▀██████████████████████████████    ")
    print("     ▀████████████████████████████▄    ▄████████████████████████████▀     ")
    print("       ▀███████████████████████████    ███████████████████████████▀       ")
    print("         ▀█████████████████████████    █████████████████████████▀         ")
    print("           ▀███████████████████████    ███████████████████████▀           ")
    print("             ▀█████████████████████    █████████████████████▀             ")
    print("               ▀███████████████████    ███████████████████▀               ")
    print("                 ▀█████████████████    █████████████████▀                 ")
    print("                    ▀██████████████    ██████████████▀                    ")
    print("                      ▀████████████    ████████████▀                      ")
    print("                        ▀██████████    ██████████▀                        ")
    print("                           ▀███████    ███████▀                           ")
    print("                             ▀▀████    ████▀▀                             ")
    print("                                ▀███  ███▀                                ")
    print("                                  ▀█▄▄█▀                                  ")
    print(f"{NC}")
    # fmt: on

    print_bar()

    orig_username = os.getlogin()

    print_title("Enabling Passwordless Sudo")
    add_line_to_file("/etc/sudoers", f"{orig_username} ALL=(ALL) NOPASSWD: ALL\n")
    print_bar()

    print_title("Checking Git Status")
    # run a few commands as the original user, so as not to break permissons
    print("Configuring credential cache")
    subprocess.check_call(
        original_user_cmd(
            orig_username, ["git", "config", "--global", "credential.helper", "cache"]
        )
    )
    print("Fetching latest code")
    subprocess.check_call(
        original_user_cmd(
            orig_username,
            [
                "git",
                f"--git-dir={os.path.join(AVR_DIR, '.git')}",
                f"--work-tree={AVR_DIR}",
                "fetch",
            ],
        ),
        cwd=AVR_DIR,
    )

    # ignore git errors, they're usually due to a missing HEAD file
    # because of weird situations
    with contextlib.suppress(subprocess.CalledProcessError):
        # check if we're on the main branch
        if not development:
            print("Making sure we're on the main branch")
            current_branch = (
                subprocess.check_output(
                    original_user_cmd(
                        orig_username, ["git", "rev-parse", "--abbrev-ref", "HEAD"]
                    ),
                    cwd=AVR_DIR,
                    stderr=subprocess.DEVNULL,
                )
                .decode("utf-8")
                .strip()
            )
            if current_branch != "main":
                print(
                    f"{LIGHTRED}WARNING:{NC} Not currently on the main branch, run 'git checkout main && git pull' then re-run this script"
                )
                sys.exit(1)

        # check if we're on the latest commit
        print("Making sure we have the latest code")
        local_commit = (
            subprocess.check_output(
                original_user_cmd(orig_username, ["git", "rev-parse", "HEAD"]),
                cwd=AVR_DIR,
            )
            .decode("utf-8")
            .strip()
        )
        upstream_commit = (
            subprocess.check_output(
                original_user_cmd(orig_username, ["git", "rev-parse", "@{u}"]),
                cwd=AVR_DIR,
            )
            .decode("utf-8")
            .strip()
        )

        if local_commit != upstream_commit:
            print(
                f"{LIGHTRED}WARNING:{NC} Remote changes exist that are not present locally. Run 'git pull' then re-run this script"
            )
            sys.exit(1)

    print("Making sure submodules are up-to-date")
    # https://stackoverflow.com/a/64621032
    subprocess.check_call(
        original_user_cmd(
            orig_username,
            [
                "git",
                f"--git-dir={os.path.join(AVR_DIR, '.git')}",
                "--work-tree=.",
                "-C",
                AVR_DIR,
                "submodule",
                "update",
                "--init",
                "--recursive",
            ],
        ),
        cwd=AVR_DIR,
    )
    print_bar()

    print_title("Adding Bash Aliases")
    bash_rc = os.path.join(HOME_DIR, ".bashrc")
    add_line_to_file(
        bash_rc, f"alias install='sudo python3 {os.path.join(AVR_DIR, 'install.py')}'\n"
    )
    add_line_to_file(
        bash_rc, f"alias start='sudo python3 {os.path.join(AVR_DIR, 'start.py')}'\n"
    )
    add_line_to_file(
        bash_rc, f"alias wifi='sudo python3 {os.path.join(AVR_DIR, 'wifi.py')}'\n"
    )
    print_bar()

    print_title("Updating Package Index")
    subprocess.check_call(["apt-get", "update"])
    print_bar()

    print_title("Upgrading System Packages")
    subprocess.check_call(
        ["apt-get", "upgrade", "-y"],
        env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
    )
    print_bar()

    print_title("Installing Prerequisites")
    # a lot of these are already installed by default
    # but better to be explicit
    packages = [
        "git",
        "ca-certificates",
        "apt-utils",
        "software-properties-common",
        "wget",
        "htop",
        "nano",
        "python3",
        "docker-compose",
    ]
    print("Installing apt Packages")
    subprocess.check_call(
        ["apt-get", "install", "-y"] + packages,
        env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
    )

    # install pip packages
    # print("Installing Python Packages")
    # subprocess.check_call(["python3", "-m", "pip", "install", "--upgrade", "pip", "wheel"], stderr=subprocess.DEVNULL)
    # subprocess.check_call(["python3", "-m", "pip", "install", "-r", os.path.join(AVR_DIR, "resources", "requirements.txt")], stderr=subprocess.DEVNULL)

    if development:
        subprocess.check_call(
            ["python3", "-m", "pip", "install", "--upgrade", "jetson-stats"],
            stderr=subprocess.DEVNULL,
        )
    print_bar()

    print_title("Configuring Jetson Settings")
    # set to high-power 10W mode. 1 is 5W mode
    print("Setting power mode")
    subprocess.check_call(["nvpmodel", "-m", "0"])

    # make sure SPI is enabled
    # header 1 is the 40pin header
    # gotten from `sudo /opt/nvidia/jetson-io/config-by-pin.py -l`
    # https://docs.nvidia.com/jetson/archives/r34.1/DeveloperGuide/text/HR/ConfiguringTheJetsonExpansionHeaders.html#config-by-function-configure-header-s-by-special-function
    print("Enabling SPI")

    # fix weird out-of-the-box issues
    # https://github.com/JetsonHacksNano/SPI-Playground

    jetson_io_root = "/opt/nvidia/jetson-io/"
    # touch __init__.py files one directory level down

    for item in os.listdir(jetson_io_root):
        if os.path.isdir(os.path.join(jetson_io_root, item)):
            pathlib.Path(os.path.join(jetson_io_root, item, "__init__.py")).touch()

    # make sure the "/boot/dtb" folder exists
    os.makedirs("/boot/dtb", exist_ok=True)

    # copy tegra210 device tree boot files
    for item in os.listdir("/boot/"):
        if re.match("tegra210-p3448-0000-p3449-0000-[ab]0[012].dtb", item):
            print(f"Copying {item}")
            shutil.copy(os.path.join("/boot/", item), "/boot/dtb/")

    # delete this file that seems to cause problems
    if os.path.isfile("/boot/dtb/kernel_tegra210-p3448-0000-p3449-0000-b00.dtb"):
        os.remove("/boot/dtb/kernel_tegra210-p3448-0000-p3449-0000-b00.dtb")

    subprocess.check_call(
        [
            "python3",
            "/opt/nvidia/jetson-io/config-by-function.py",
            "-o",
            "dtb",
            "1=spi1",
        ]
    )
    print_bar()

    print_title("Removing Old Docker Data")
    print("Removing old Docker containers")
    containers = (
        subprocess.check_output(["docker", "container", "ps", "-a", "-q"])
        .decode("utf-8")
        .splitlines()
    )
    for container in containers:
        subprocess.check_call(["docker", "container", "rm", "-f", container])

    print("Removing old Docker volumes")
    volumes = (
        subprocess.check_output(["docker", "volume", "ls", "-q"])
        .decode("utf-8")
        .splitlines()
    )
    for volume in volumes:
        subprocess.check_call(["docker", "volume", "rm", volume])
    print_bar()

    # print_title("Installing Docker Compose")
    # subprocess.check_call(["python3", "-m", "pip", "install", "--upgrade", "docker-compose"], stderr=subprocess.DEVNULL)
    # print_bar()

    print_title("Configuring the Nvidia Docker Runtime")
    # set the nvidia runtime to be default
    # https://lukeyeager.github.io/2018/01/22/setting-the-default-docker-runtime-to-nvidia.html
    daemon_json = "/etc/docker/daemon.json"
    with open(daemon_json, "r") as fp:
        daemon_data = json.load(fp)

    if daemon_data.get("default-runtime", "") != "nvidia":
        print(f"Updating {daemon_json}")

        daemon_data["default-runtime"] = "nvidia"
        assert "nvidia" in daemon_data["runtimes"]

        with open(daemon_json, "w") as fp:
            json.dump(daemon_data, fp, indent=2)

    # needed so that the shared libs are included in the docker container creation from the host
    print("Copying Docker runtime libraries definition")
    shutil.copy(
        os.path.join(AVR_DIR, "resources/avr-nvidia-libraries.csv"),
        "/etc/nvidia-container-runtime/host-files-for-container.d/",
    )

    # restart docker so new runtime takes into effect
    print("Restarting Docker service")
    subprocess.check_call(["service", "docker", "stop"])
    subprocess.check_call(["service", "docker", "start"])
    print_bar()

    print_title("Installing Boot Services")
    services = ["spio-mount.service", "fan-100.service"]
    for service in services:
        print(f"Installing {service}")
        shutil.copy(os.path.join(AVR_DIR, "resources", service), "/etc/systemd/system/")
        # SPI mount service will not work until Jetson is rebooted after enabling SPI
        subprocess.run(
            ["systemctl", "enable", service], check=service != "spio-mount.service"
        )
        subprocess.run(
            ["systemctl", "start", service], check=service != "spio-mount.service"
        )
    print_bar()

    print_title("Obtaining ZED Camera Configuration")
    zed_settings_dir = os.path.join(AVR_DIR, "modules/vio/settings")

    zed_serial = (
        subprocess.check_output(
            [
                "docker",
                "run",
                "--rm",
                "--mount",
                f"type=bind,source={zed_settings_dir},target=/usr/local/zed/settings/",
                "--privileged",
                "docker.io/stereolabs/zed:3.7-py-runtime-l4t-r32.6",
                "python3",
                "-c",
                "import pyzed.sl;z=pyzed.sl.Camera();z.open();print(z.get_camera_information().serial_number);z.close();",
            ]
        )
        .decode("utf-8")
        .strip()
    )
    if zed_serial == "0":
        print(
            f"{LIGHTRED}WARNING:{NC} ZED camera not detected, skipping settings download"
        )
    else:
        print("ZED camera settings have been downloaded")
    print_bar()

    # make sure at least one settings file exists
    if not development and not any(
        f.endswith(".conf") for f in os.listdir(zed_settings_dir)
    ):
        print(
            f"{RED}ERROR:{NC} ZED settings not found. Your drone will NOT fly. Plug in the ZED camera and try again."
        )
        sys.exit(1)

    print_title("Building AVR Software")
    # make sure docker is logged in
    proc = subprocess.run(["docker", "pull", "ghcr.io/nathanvaughn/avr/mavp2p:latest"])
    if proc.returncode != 0:
        print("Please log into GitHub container registry:")
        subprocess.check_call(["docker", "login", "ghcr.io"])

    # pull images
    cmd = ["python3", os.path.join(AVR_DIR, "start.py"), "pull", "--norm"]
    if development:
        cmd.append("--local")
    subprocess.check_call(cmd)

    # build images
    cmd = ["python3", os.path.join(AVR_DIR, "start.py"), "build", "--norm"]
    if development:
        cmd.append("--local")
    subprocess.check_call(cmd)
    print_bar()

    print_title("Cleaning Up")
    # remove some extra software
    subprocess.check_call(
        [
            "apt-get",
            "purge",
            "vlc*",
            "leafpad",
            "rhythmbox*",
            "thunderbird",
            "libreoffice*",
            "-y",
        ]
    )
    subprocess.check_call(["apt-get", "autoremove", "-y"])
    subprocess.check_call(["docker", "system", "prune", "-f"])
    print_bar()

    print_title("Performing Self-Test")
    print("Testing Nvidia container runtime:")
    proc = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--gpus",
            "all",
            "--env",
            "NVIDIA_DISABLE_REQUIRE=1",
            "nvcr.io/nvidia/cuda:11.4.1-base-ubuntu18.04",
            "echo",
            "-e",
            f"{LIGHTGREEN}Passed!{NC}",
        ]
    )
    if proc.returncode != 0:
        print(f"{LIGHTRED}FAILED{NC}")
    print_bar()

    print(f"{GREEN}AVR setup has completed{NC}")
    print(f"{GREEN}Please reboot your VMC{NC}")

    if input("Would you like to reboot now? (y/n): ").lower() == "y":
        subprocess.run(["reboot"])


if __name__ == "__main__":
    check_sudo(__file__)

    parser = argparse.ArgumentParser(description="Setup the Jetson for AVR")
    parser.add_argument(
        "--development", "--dev", action="store_true", help="Development setup"
    )

    args = parser.parse_args()
    main(args.development)
