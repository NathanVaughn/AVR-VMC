import os
import sys
import subprocess


def check_sudo(original_file) -> None:
    # skip these checks on Windows
    if sys.platform == "win32":
        return

    if os.geteuid() != 0:
        # re run ourselves with sudo
        print("Needing sudo privileges, re-launching")

        try:
            sys.exit(
                subprocess.run(
                    ["sudo", sys.executable, os.path.realpath(original_file)]
                    + sys.argv[1:]
                ).returncode
            )
        except PermissionError:
            sys.exit(0)
        except KeyboardInterrupt:
            sys.exit(1)
