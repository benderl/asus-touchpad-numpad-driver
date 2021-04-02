from libevdev import Device, InputEvent, EV_ABS, EV_KEY, EV_LED, EV_SYN
from fcntl import fcntl, F_SETFL
from time import sleep
import sys
from os import O_NONBLOCK
import subprocess

onCmd = "i2ctransfer -f -y 2 w13@0x15 0x05 0x00 0x3d 0x03 0x06 0x00 0x07 0x00 0x0d 0x14 0x03 0x01 0xad"
offCmd = "i2ctransfer -f -y 2 w13@0x15 0x05 0x00 0x3d 0x03 0x06 0x00 0x07 0x00 0x0d 0x14 0x03 0x00 0xad"
numlock=False
tries=5

# Look into the devices file #
while tries > 0:

    keyboard_detected = 0
    touchpad_detected = 0
        
    with open('/proc/bus/input/devices', 'r') as f:
    
        lines = f.readlines()
        for line in lines:
            # Look for the touchpad #
            if touchpad_detected == 0 and "Name=\"ELAN" in line and "Mouse" not in line:
                touchpad_detected = 1
    
            if touchpad_detected == 1:
                if "H: " in line:
                    touchpad = line.split("event")[1]
                    touchpad = touchpad.split(" ")[0]
                    touchpad_detected = 2

            # Look for the keyboard (numlock) # AT Translated Set
            if keyboard_detected == 0 and "Name=\"AT Translated Set 2 keyboard" in line:
                keyboard_detected = 1
    
            if keyboard_detected == 1:
                if "H: " in line:
                    keyboard = line.split("event")[1]
                    keyboard = keyboard.split(" ")[0]
                    keyboard_detected = 2

            # Stop looking if both have been found #
            if keyboard_detected == 2 and touchpad_detected == 2:
                break
    
    if keyboard_detected != 2 or touchpad_detected != 2:
        tries -= 1
        if tries == 0:
            if keyboard_detected != 2:
                print("Can't find keyboard, code " + str(keyboard_detected))
            if touchpad_detected != 2:
                print("Can't find touchpad, code " + str(touchpad_detected))                    
            sys.exit(1)
    else:
        break

    sleep(0.1)


# Start monitoring the touchpad #
fd_t = open('/dev/input/event' + str(touchpad), 'rb')
fcntl(fd_t, F_SETFL, O_NONBLOCK)
d_t = Device(fd_t)
# Retrieve touchpad dimensions #
ai = d_t.absinfo[EV_ABS.ABS_X]
(minx, maxx) = (ai.minimum, ai.maximum)
ai = d_t.absinfo[EV_ABS.ABS_Y]
(miny, maxy) = (ai.minimum, ai.maximum)

# Start monitoring the keyboard (numlock) #
fd_k = open('/dev/input/event' + str(keyboard), 'rb')
fcntl(fd_k, F_SETFL, O_NONBLOCK)
d_k = Device(fd_k)

# Create a new keyboard device to send numpad events #
dev = Device()
dev.name = "Asus Touchpad/Numpad"
dev.enable(EV_KEY.KEY_KP1)
dev.enable(EV_KEY.KEY_KP2)
dev.enable(EV_KEY.KEY_KP3)
dev.enable(EV_KEY.KEY_KP4)
dev.enable(EV_KEY.KEY_KP5)
dev.enable(EV_KEY.KEY_KP6)
dev.enable(EV_KEY.KEY_7)
dev.enable(EV_KEY.KEY_KP8)
dev.enable(EV_KEY.KEY_KP9)
dev.enable(EV_KEY.KEY_KP0)
dev.enable(EV_KEY.KEY_BACKSPACE)
dev.enable(EV_KEY.KEY_KPSLASH)
dev.enable(EV_KEY.KEY_KPASTERISK)
dev.enable(EV_KEY.KEY_KPMINUS)
dev.enable(EV_KEY.KEY_KPPLUS)
dev.enable(EV_KEY.KEY_KPCOMMA)
dev.enable(EV_KEY.KEY_KPENTER)
dev.enable(EV_KEY.KEY_LEFTSHIFT)

udev = dev.create_uinput_device()

finger = 0
value = 0

# Process events while running #
while True:

    # If keyboard sends numlock event with F8 key tap, enable/disable touchpad events #
    for e in d_k.events():
        if e.matches(EV_KEY.KEY_F8) and e.value == 1:
            numlock = not numlock
            if numlock:
                d_t.grab()
                subprocess.call(onCmd, shell=True)
            else:
                d_t.ungrab()
                subprocess.call(offCmd, shell=True)

    # If touchpad sends tap events, convert x/y position to numlock key and send it #
    for e in d_t.events():

        # If touchpad mode, ignore #
        if not numlock:
            continue
        
        # Get x position #
        if e.matches(EV_ABS.ABS_MT_POSITION_X) and finger == 0:
            x = e.value
        
        # Get y position #
        if e.matches(EV_ABS.ABS_MT_POSITION_Y) and finger == 0:
            y = e.value

        # If tap #
        if e.matches(EV_KEY.BTN_TOOL_FINGER):
            # If end of tap, send release key event #
            if e.value == 0:
                finger = 0
                try:
                    events = [
                        InputEvent(EV_KEY.KEY_LEFTSHIFT, 0),
                        InputEvent(value, 0),
                        InputEvent(EV_SYN.SYN_REPORT, 0)
                    ]
                    udev.send_events(events)
                    pass
                except OSError as e:
                    pass

            # Start of tap #
            if finger == 0 and e.value == 1:
                finger = 1

        # During tap #
        if finger == 1:
            finger = 2

            try:
                events = []
                # first row
                if y < 0.25 * maxy:
                    # nums colums
                    if x < 0.2 * maxx:
                        value = EV_KEY.KEY_7
                    elif x < 0.4 * maxx:
                        value = EV_KEY.KEY_KP8
                    elif x < 0.6 * maxx:
                        value = EV_KEY.KEY_KP9
                    elif x < 0.8 * maxx:
                        value = EV_KEY.KEY_KPSLASH
                    else:
                        value = EV_KEY.KEY_BACKSPACE
                # second row
                elif y < 0.5 * maxy:
                    if x < 0.2 * maxx:
                        value = EV_KEY.KEY_KP4
                    elif x < 0.4 * maxx:
                        value = EV_KEY.KEY_KP5
                    elif x < 0.6 * maxx:
                        value = EV_KEY.KEY_KP6
                    elif x < 0.8 * maxx:
                        value = EV_KEY.KEY_KPASTERISK
                    else:
                        value = EV_KEY.KEY_BACKSPACE
                # third row
                elif y < 0.75 * maxy:
                    if x < 0.2 * maxx:
                        value = EV_KEY.KEY_KP1
                    elif x < 0.4 * maxx:
                        value = EV_KEY.KEY_KP2
                    elif x < 0.6 * maxx:
                        value = EV_KEY.KEY_KP3
                    elif x < 0.8 * maxx:
                        value = EV_KEY.KEY_KPMINUS
                    else:
                        value = EV_KEY.KEY_KPENTER
                # last row
                else:
                    if x < 0.4 * maxx:
                        value = EV_KEY.KEY_KP0
                    elif x < 0.6 * maxx:
                        value = EV_KEY.KEY_KPCOMMA
                    elif x < 0.8 * maxx:
                        value = EV_KEY.KEY_KPPLUS
                    else:
                        value = EV_KEY.KEY_KPENTER

                # Send press key event #
                events.append(InputEvent(EV_KEY.KEY_LEFTSHIFT, 1))
                events.append(InputEvent(value, 1))
                events.append(InputEvent(EV_SYN.SYN_REPORT, 0))
                udev.send_events(events)
            except OSError as e:
                pass
    sleep(0.1)

# Close file descriptors #
fd_k.close()
fd_t.close()