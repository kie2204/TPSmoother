#!/usr/bin/env python3

import asyncio
from threading import Event
import argparse, queue
import time
from evdev import InputDevice, UInput, ecodes, events

parser = argparse.ArgumentParser()
parser.add_argument(
    "-d",
    "--device",
    help="Input device to use. (e.g. /dev/input/event1)",
    required=True
)
parser.add_argument(
    "-g",
    "--grab",
    action="store_true",
    help="Grab the input device. Blocks other applications from recieving the real input.",
)
parser.add_argument(
    "-m",
    "--multiplier",
    type=int,
    default=3,
    help="Event multiplier, i.e. how many smoothed virtual events should be generated from one real input event.",
)
parser.add_argument(
    "-f",
    "--min-frequency",
    type=int,
    default=30,
    help="Minimum smoothing frequency. When real input frequency is below this value, the smoothing timer is forcibly set based on the specified minimum frequency."
)
parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="Log verbose output in terminal."
)

def gen_rel_events(queue: queue.Queue[events.RelEvent], multiplier: int) -> tuple[list[events.RelEvent]]:
    event_list = []
    while queue.qsize() != 0:
        event = queue.get()
        event_list.append(event)

    out = (event_list,) * multiplier
    return out


def get_capabilities_str(device: InputDevice):
    caps = device.capabilities()
    ecode = lambda t, c: ecodes.bytype[t][c]
    
    out = []

    for etype, codes in caps.items():
        out.append(f"  {ecodes.EV[etype]}:")
        for code in codes:
            if type(code) is int:
                out.append(f"    {ecode(etype, code)}")
            elif type(code) is tuple:
                out.append(f"    {(ecode(etype, code[0]), *code[1:])}")
            else:
                out.append(f"    {code}")
                
    return '\n'.join(out)

verbose = False
def logv(*values):
    if verbose:
        print(*values)

def main(args):
    device = InputDevice(args.device)

    print(f"Using device {args.device} - {device.name}")
    logv("Supported capabilities:")
    logv(get_capabilities_str(device))
    
    print(f"Smoothing with {args.multiplier}x multiplier.")

    # Create virtual device
    ui = UInput.from_device(device, name=f"{device.name} (TPSmoother)")
    print(f"Created virtual device {ui.devnode} - {ui.name}")

    if args.grab:
        print(f"Argument --grab specified, blocking real input.")
        device.grab()

    rel_queue = queue.Queue()
    abs_queue = queue.Queue()
    event_queue = queue.Queue()
    
    last_counter = None
    
    logv("Verbose output specified, input events will be logged in terminal.")
    for event in device.read_loop():
        logv(
            ecodes.EV[event.type],
            ecodes.bytype[event.type][event.code],
            event.value,
        )
        if event.type == ecodes.EV_REL:
            rel_queue.put(event)
        elif event.type == ecodes.EV_ABS:
            abs_queue.put(event)
        else:
            event_queue.put(event)

        if event.type == ecodes.EV_SYN:
            rel_smoothed_events = gen_rel_events(rel_queue, args.multiplier)
            
            for rel_event in rel_smoothed_events[0]:
                ui.write(rel_event.type, rel_event.code, rel_event.value)

            qevent = event_queue.get()
            while qevent.type != ecodes.EV_SYN:
                ui.write(qevent.type, qevent.code, qevent.value)
                qevent = event_queue.get()
            
            ui.syn()
            logv(f"-- SYN ({ecodes.bytype[event.type][event.code]}) --")
                
            frequency: int
            counter = time.perf_counter()
            if last_counter is None:
                frequency = 60
            else:
                delta = time.perf_counter() - last_counter
                frequency = 1 / delta
                
            last_counter = counter
            logv(frequency)
                
            if frequency < args.min_frequency:
                frequency = args.min_frequency
            delay = 1 / (frequency * args.multiplier)
            for i in range(1, args.multiplier):
                time.sleep(delay)
                
                for rel_event in rel_smoothed_events[i]:
                    ui.write(rel_event.type, rel_event.code, rel_event.value)
                
                ui.syn()


if __name__ == "__main__":
    args=parser.parse_args()
    verbose = args.verbose
    main(args)
