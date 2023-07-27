# RSS-Demonstrator
RSS Safety Model Demonstrator

This demonstrator requires a CARLA build that includes RSS.
For testing purposes, it is also possible to run it with a prebuilt CARLA without RSS. Use commandline parameter ```--norss```

## Setup

    git submodule update --init
    sudo apt install python-pexpect jstest-gtk
    pip install --user -r carla-scenario-runner/requirements.txt
    pip install --user evdev pygame


The demo looks for the Logitech G29 wheel under the name ```/dev/logitech_raw```.
The most convenient way to properly configure the wheel is the udev rules file provided.

Copy the file ```99-logitech-g29.rules``` into folder ```/etc/udev/rules.d/```, then ```sudo udevadm control --reload``` and dis- and reconnect the device.

It is now automatically symlinked as ```/dev/logitech_g29``` and ```/dev/logitech_raw```.

After this you can calibrate the wheel using jstest-gtk

    jstest-gtk /dev/logitech_raw


## Execution

This demo is optimized for a resolution of 1920x1080.

     export PYTHONPATH=$PYTHONPATH:<path-to-carla>/PythonAPI/carla/dist/carla-<carla_version_and_arch>.egg:<path-to-carla>/PythonAPI/carla/:./lib:./dialogs
    ./manual_control_rss_demo.py --res 1920x1080


### Available controls


| Key | Description |
|-----|-------------|
| U   | Move the ego vehicle to the next CARLA waypoint (e.g. if it's off the road). Keep in mind: If the car is heading into the opposite direction, the waypoint might be on the other side of the road. |
| I   | Pause the simulation. |
| F   | Toggle Fullscreen Mode |
| R   | Toggle if RSS should restrict the control |
| RETURN | Continue on dialog. (Similar to red button of steering wheel) |
| F1 | Display detailed RSS Information |
| F5 | Trigger demo scenario |
| F6 | Trigger demo scenario with starting point after first corner |
| F7 | Trigger demo scenario with starting point after the second corner |
| F8 | Trigger demo scenario with starting point after the third corner |
| F9 | Trigger demo scenario with starting point after the third corner, after pedestrians |
| CTRL + Q | Quit demo |


### Possible Use cases

#### Analyzing a stucked situation

In case a user cannot proceed (because rss restricts any movement), you might want to explain the current situation.

1. Pause simulation by pressing <I>
2. Display the detailed RSS information by pressing <F1>
3. Clarify RSS Model Behavior
4. Respawn user

