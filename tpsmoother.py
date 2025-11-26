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
    required=True,
)
parser.add_argument(
    "-g",
    "--grab",
    action="store_true",
    help="Grab the input device. Blocks other applications from recieving the real input.",
)
parser.add_argument(
    "-t",
    "--target-hz",
    type=int,
    default=120,
    help="Target minimum frequency for virtual input device. The multiplier will be adjusted dynamically to achieve the specified polling rate.",
)
parser.add_argument(
    "-m",
    "--multiplier",
    type=int,
    default=None,
    help="Static event multiplier, i.e. how many smoothed virtual events should be generated from one real input event. Overrides --target-hz.",
)
parser.add_argument(
    "-f",
    "--min-frequency",
    type=int,
    default=30,
    help="Minimum smoothing frequency. When real input frequency is below this value, the smoothing timer is forcibly set based on the specified minimum frequency.",
)
parser.add_argument(
    "-v", "--verbose", action="store_true", help="Log verbose output in terminal."
)

def ecopy(event: events.InputEvent) -> events.InputEvent:
    return events.InputEvent(event.sec, event.usec, event.type, event.code, event.value)

def gen_rel_events(
    queue: queue.Queue[events.RelEvent], multiplier: int
) -> tuple[list[events.RelEvent]]:
    event_list = []
    while queue.qsize() != 0:
        event = queue.get()
        event_list.append(ecopy(event))

    out = (event_list,) * multiplier
    return out


ABS_SMOOTHING_WHITELIST = [
    ecodes.ABS_PRESSURE,
    ecodes.ABS_X,
    ecodes.ABS_Y,
]

ABS_MT_SMOOTHING_WHITELIST = [
    ecodes.ABS_MT_POSITION_X,
    ecodes.ABS_MT_POSITION_Y,
    ecodes.ABS_MT_PRESSURE,
]

last_abs_events: dict[int, events.AbsEvent] = dict() # event.code -> event
last_abs_mt_events: dict[int, dict[int, events.AbsEvent]] = dict() # abs_mt_slot -> event.code -> event
last_mt_slot: int = 0

def lerp(x: int, y: int, weight: float):
    return x * (1 - weight) + y * weight

def gen_abs_events(
    queue: queue.Queue[events.AbsEvent], multiplier: int
) -> tuple[list[events.AbsEvent]]:
    global last_mt_slot

    # Process initial event
    initial_events = []
    
    initial_smoothable_events = dict()
    initial_smoothable_mt_events = dict()
    
    final_smoothable_events = dict()
    final_smoothable_mt_events = dict()
    
    while queue.qsize() != 0:
        event = queue.get()
        event_initial_copy = ecopy(event)
        event_final_copy = ecopy(event)
        initial_events.append(event_initial_copy)
        
        if event.code == ecodes.ABS_MT_SLOT:
            last_mt_slot = event.value
        
        if (event.code == ecodes.ABS_MT_TRACKING_ID and event.value == -1) or event.code == ecodes.BTN_TOOL_DOUBLETAP:
            last_abs_events.clear()
            last_abs_mt_events.clear()
            last_mt_slot = 0
        
        if event.code in ABS_SMOOTHING_WHITELIST:
            initial_smoothable_events[event.code] = event_initial_copy
            final_smoothable_events[event.code] = event_final_copy
            
        if event.code in ABS_MT_SMOOTHING_WHITELIST:
            if initial_smoothable_mt_events.get(last_mt_slot) is None: 
                initial_smoothable_mt_events[last_mt_slot] = dict()
                
            if final_smoothable_mt_events.get(last_mt_slot) is None: 
                final_smoothable_mt_events[last_mt_slot] = dict()
                
            initial_smoothable_mt_events[last_mt_slot][event.code] = event_initial_copy
            final_smoothable_mt_events[last_mt_slot][event.code] = event_final_copy
            

    out = (initial_events,) + tuple([list() for _ in range(multiplier-1)])
    
    for mt_slot, mt_events in initial_smoothable_mt_events.items():
        slot_last_events = last_abs_mt_events.setdefault(mt_slot, dict()) 
        slot_final_events = final_smoothable_mt_events.get(mt_slot)
        
        if len(mt_events) == 0:
            slot_last_events.clear()
            break
        
        for i in range(1, multiplier):
            slot_event = events.InputEvent(None, None, ecodes.EV_ABS, ecodes.ABS_MT_SLOT, mt_slot)
            out[i].append(slot_event)
        
        for event in mt_events.values():
            slot_last_event = slot_last_events.get(event.code)
            slot_last_events[event.code] = ecopy(event)
            if slot_last_event is None:
                slot_final_events.pop(event.code)
            else:
                original_value = event.value
                event.value = int(lerp(slot_last_event.value, original_value, 1/multiplier))
                
                # Intermediate smoothing events
                for i in range(1, multiplier-1):
                    i_value = int(lerp(slot_last_event.value, original_value, (i+1)/multiplier))
                    i_event = ecopy(event)
                    i_event.value = i_value
                    out[i].append(i_event)
        
        for event in slot_final_events.values():
            out[multiplier - 1].append(event)
            
    
    # Generate initial smoothed event
    for event in initial_smoothable_events.values():
        last_abs_event = last_abs_events.get(event.code)
        last_abs_events[event.code] = ecopy(event)
        if last_abs_event is None:
            final_smoothable_events.pop(event.code)
        else:
            original_value = event.value
            event.value = int(lerp(last_abs_event.value, original_value, 1/multiplier))
            
            # Intermediate smoothing events
            for i in range(1, multiplier-1):
                i_value = int(lerp(last_abs_event.value, original_value, (i+1)/multiplier))
                i_event = ecopy(event)
                i_event.value = i_value
                out[i].append(i_event)
            
    
    # Final smoothed event
    for event in final_smoothable_events.values():
        out[multiplier - 1].append(event)
        
    # Print virtual events (for testing)
    # i = 0
    # for evs in out:
    #     print(f"Virtual event {i}:")
    #     i += 1
    #     for event in evs:
    #         print(f"  {event_str(event)}")
    return out


def get_capabilities_str(device: InputDevice):
    caps = device.capabilities()
    ecode = lambda t, c: ecodes.bytype.get(t, []).get(c, f"? ({c})") 

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

    return "\n".join(out)


verbose = False


def logv(*values):
    if verbose:
        print(*values)


def event_str(event: events.InputEvent):
    return (
        f"{ecodes.EV[event.type]} {ecodes.bytype[event.type][event.code]} {event.value}"
    )


def main(args):
    device = InputDevice(args.device)

    print(f"Using device {args.device} - {device.name}")
    logv("Supported capabilities:")
    logv(get_capabilities_str(device))

    if args.multiplier is None:
        print(f"Smoothing to {args.target_hz}Hz target.")
    else:
        print(f"Smoothing with static multiplier ({args.multiplier}x).")

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
        logv(event_str(event))
        if event.type == ecodes.EV_REL:
            rel_queue.put(event)
        elif event.type == ecodes.EV_ABS:
            abs_queue.put(event)
        else:
            event_queue.put(event)

        if event.type == ecodes.EV_SYN:
            frequency: float
            multiplier: int
            
            counter = time.perf_counter()
            if last_counter is None:
                frequency = args.min_frequency
            else:
                delta = time.perf_counter() - last_counter
                frequency = 1 / delta

            last_counter = counter
            logv(frequency)

            if frequency < args.min_frequency:
                frequency = args.min_frequency
            
            if args.multiplier is None:
                multiplier = int(args.target_hz / frequency) + 1
            else:
                multiplier = args.multiplier
            
            rel_smoothed_events = gen_rel_events(rel_queue, multiplier)
            abs_smoothed_events = gen_abs_events(abs_queue, multiplier)

            for rel_event in rel_smoothed_events[0]:
                ui.write(rel_event.type, rel_event.code, rel_event.value)

            for abs_event in abs_smoothed_events[0]:
                ui.write(abs_event.type, abs_event.code, abs_event.value)

            qevent = event_queue.get()
            while qevent.type != ecodes.EV_SYN:
                ui.write(qevent.type, qevent.code, qevent.value)
                qevent = event_queue.get()

            ui.syn()
            logv(f"-- SYN ({ecodes.bytype[event.type][event.code]}) --")

            # After original event, send smoothed events    
            delay = 1 / (frequency * multiplier)
            for i in range(1, multiplier):
                time.sleep(delay)

                for rel_event in rel_smoothed_events[i]:
                    ui.write(rel_event.type, rel_event.code, rel_event.value)

                for abs_event in abs_smoothed_events[i]:
                    ui.write(abs_event.type, abs_event.code, abs_event.value)

                ui.syn()


if __name__ == "__main__":
    args = parser.parse_args()
    verbose = args.verbose
    main(args)
