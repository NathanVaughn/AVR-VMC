# AVR-VMC

## Setup

Run the following commands:

```bash
git clone --recurse-submodules https://github.com/nathanvaughn/AVR-VMC ~/AVR-VMC
cd ~/AVR-VMC
chmod +x install.py
./install.py
```

Please note, this setup script WILL take a while the first time
(depending on your download speed).

If you have problems with the setup script, ensure that the following
domains are not blocked. Some schools or networks may restrict these:

```bash
# created with `sudo tcpdump -w dnsrequests.pcap -i any udp and port 53`
# and loaded into Wireshark

# code distribution
github.com
*.githubusercontent.com

# stereo labs camera configuration
*.stereolabs.com

# system packages and services
*.ubuntu.com
*.nvidia.com
api.snapcraft.io
*.launchpad.net
deb.nodesource.com

# python packages
pypi.python.org
pypi.org
files.pythonhosted.org

# Docker registries
*.docker.io
*.docker.com
nvcr.io
ghcr.io

# various CDN providers
*.cloudfront.net
*.akamaized.net
*.akamai.net
*.akamaiedge.net
*.fastly.net
*.edgekey.net
```

This may not be an exhaustive list, as upstream sources may change CDNs or domain names.

## Usage

To start the AVR software, just run:

```bash
./start.py run
```

To stop the AVR software hit <kbd>Ctrl</kbd>+<kbd>C</kbd>.

Additionally, you can specify specific containers by declaring them as folows:

```bash
./start.py run thermal status -m
```

this will run all of the minimum modules required for flight (-m = [fcm, fusion, mavp2p, mqtt, vio]) in addition to the thermal & status modules

If you ever need to update the AVR software, run:

```bash
# Update the git repo
git pull --recurse-submodules
# Re-run the setup script
./install.py
```
