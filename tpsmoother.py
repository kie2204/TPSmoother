#!/usr/bin/env python3

import argparse
from evdev import InputDevice, UInput, ecodes

parser = argparse.ArgumentParser()
parser.add_argument(
    "-d", "--device", help="Input device to use. (e.g. /dev/input/event1)"
)
parser.add_argument(
    "-g",
    "--grab",
    action="store_true",
    help="Grab the input device. Blocks other applications from recieving the real input.",
)


def print_capabilites(device: InputDevice):
    caps = device.capabilities()
    ecode = lambda t, c: ecodes.bytype[t][c]

    for etype, codes in caps.items():
        print(f"  {ecodes.EV[etype]}:")
        for code in codes:
            if type(code) is int:
                print(f"    {ecode(etype, code)}")
            elif type(code) is tuple:
                print(f"    {(ecode(etype, code[0]), *code[1:])}")
            else:
                print(f"    {code}")


def main(args=parser.parse_args("")):
    device = InputDevice(args.device)

    print(f"Using device {args.device} - {device.name}")
    print("Supported capabilities:")
    print_capabilites(device)

    # Create virtual device
    ui = UInput.from_device(device, name=f"{device.name} (TPSmoother)")

    if args.grab:
        device.grab()

    # Event loop, forward real events 1:1
    for event in device.read_loop():
        if event.type == ecodes.EV_SYN:
            print("-- SYN --")
            ui.syn()
        else:
            print(
                ecodes.EV[event.type],
                ecodes.bytype[event.type][event.code],
                event.value,
            )
            ui.write(event.type, event.code, event.value)


if __name__ == "__main__":
    main(args=parser.parse_args())
