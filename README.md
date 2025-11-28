# TPSmoother
A script to improve the smoothness of pointing devices with low polling rate on Linux (e.g. TrackPoint or touchpad)

## How to use

### Prerequisites
You will need Python 3 to run this Python script. If you do not have it, install it from your favorite package manager.

You will also need the module `python-evdev`. Install from package manager or pip, as described in [python-evdev documentation](https://python-evdev.readthedocs.io/en/latest/install.html).
### Example usage
First, locate the path of your input device (touchpad, TrackPoint, etc.), usually located under `/dev/input/`. If you use libinput, you can list available devices with the command `libinput list-devices`.

Ensure the script is set as executable:
```bash
chmod +x tpsmoother.py
```

Running the script for a touchpad with path `/dev/input/event6`:
```bash
./tpsmoother.py -d /dev/input/event6 -g
```
Then you will see the following terminal output:
```
Using device /dev/input/event6 - SynPS/2 Synaptics TouchPad
Smoothing to 120Hz target.
Created virtual device /dev/uinput - SynPS/2 Synaptics TouchPad (TPSmoother)
Argument --grab specified, blocking real input.
```
The smoothed output is now being output to a virtual device, which should be ready to use immediately. 

### Arguments
This menu can be displayed by running `./tpsmoother.py -h`:
```
usage: tpsmoother.py [-h] -d DEVICE [-g] [-t TARGET_HZ] [-m MULTIPLIER] [-f MIN_FREQUENCY] [-v]

options:
  -h, --help            show this help message and exit
  -d, --device DEVICE   Input device to use. (e.g. /dev/input/event1)
  -g, --grab            Grab the input device. Blocks other applications 
                        from recieving the real input.
  -t, --target-hz TARGET_HZ
                        Target minimum frequency for virtual input device. 
                        The multiplier will be adjusted dynamically to 
                        achieve the specified polling rate.
  -m, --multiplier MULTIPLIER
                        Static event multiplier, i.e. how many smoothed 
                        virtual events should be generated from one real 
                        input event. Overrides --target-hz.
  -f, --min-frequency MIN_FREQUENCY
                        Minimum smoothing frequency. When real input 
                        frequency is below this value, the smoothing timer 
                        is forcibly set based on the specified minimum 
                        frequency.
  -v, --verbose         Log verbose output in terminal.
```