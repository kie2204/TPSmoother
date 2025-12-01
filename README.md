# TPSmoother
A script to improve the smoothness of pointing devices with low polling rate on Linux (e.g. TrackPoint or touchpad)

> [!NOTE]
> Early development, there may be bugs, missing features, or compatibility issues with some devices.

## About
TPSmoother reads input events from your real device (like a touchpad, TrackPoint or mouse) and generates a stream of virtual events at a set multiplier, which is then output to a virtual device that mimics your real device. 

It uses simple smoothing algorithms, with timing calculated based on previous events. In theory, it should add less than 1 tick of latency (e.g. for a 40Hz input, added latency is less than 1/40 s = 0.025 s).
- For relative input devices, the real events are simply duplicated according to the set multiplier. The events are then sent out with consistent delays, making a smooth transition to the next tick. Note: the effective movement is also multiplied, so sensitivity will need to be adjusted.
- For absolute input devices, linear interpolation is used to generate the virtual events. The script interpolates between the last position event and the current event, generating intermediate points according to set multiplier. Same as with relative devices, the events are sent with a consistent delay to transition smoothly to the next real tick. 

### Compatibility

- ✅ Relative input devices (TrackPoint or mouse)
- ✅ Absolute input devices (Touchpad)
- ⏺️ Multitouch inputs ([Only Type B supported](https://docs.kernel.org/input/multi-touch-protocol.html))

The script is made for (and tested on) the Lenovo L14 Gen 1 AMD, a device with incomplete touchpad support in Linux. Likely due to PS/2 protocol fallback, polling rate is capped at 40Hz for both TrackPoint and touchpad (only during multitouch gestures). With the script running for both inputs, mouse movements are much smoother with only slight added latency.

Of course, the logic in the script is not specific to any model, so it should work fine with most pointing devices. For now only Type B devices are supported for multitouch, but likely not an issue since Type A has become obsolete.

## How to use

### Prerequisites
You will need Python 3 to run this Python script. If you do not have it, install it from your favorite package manager.

You will also need the module `python-evdev`. Install from package manager or pip, as described in [python-evdev documentation](https://python-evdev.readthedocs.io/en/latest/install.html).

### Example usage
First, locate the path of your input device (touchpad, TrackPoint, etc.), usually named as `/dev/input/eventX`. If you use libinput, you can list available devices with the command `libinput list-devices`.

Alternatively, for more consistent paths, you should be able to find your device under `/dev/input/by-path/`. For example, your touchpad could be named as `/dev/input/by-path/platform-i8042-serio-1-event-mouse`.

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
