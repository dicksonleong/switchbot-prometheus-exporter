# SwitchBot Prometheus Exporter

Get the sensor data from a SwitchBot meter and expose the data as Prometheus metrics.

Inspired by https://github.com/louisblin/prometheus-switchbot-exporter but with a few differences:
- Use `bleak` instead of `bluepy` library to interact with Bluetooth
- Only perform BLE scanning when scraping by Prometheus 
- Container (especially podman) friendly

## Usage

Get the Bluetooth MAC address of your SwitchBot meter using the official SwitchBot app (under "Settings" > "Device Info").

Using Podman:

```shell
podman build . -t switchbot-prometheus-exporter

podman run --rm \
  --name switchbot-prometheus-exporter \
  --userns=keep-id \
  -p 8080:8080 \
  -v /run/dbus:/run/dbus:ro \
  localhost/switchbot-prometheus-exporter:latest \
  --device-addr "<YOUR DEVICE ADDRESS HERE>"
```

`userns=keep-id` is required for interact with Bluetooth using D-Bus.

Using uv:

```shell
uv sync
uv run main.py --device-addr "<YOUR DEVICE ADDRESS HERE>"
```

Then try to scrap the metrics:

```shell
curl http://localhost:8080/metrics
```

The scraping can take some time (>5s) if your area have a lot of BLE devices. By default it will timeout after 10s 
and it can be configured using `--scan-timeout` parameter. I recommend scrap every 5 minutes.

## How it works

When the app is started, it will listen to port 8080 by default. When the `/metrics` endpoint is called by Prometheus,
it will begin BLE scanning and search for the given device. Once it found the device, it will immediately stop the 
scanning, parse the Bluetooth AdvertisementData and return the battery, temperature and humidity in the metrics response. 

The reason why I don't want to do constant BLE scanning is I primarily run this on my low-powered homelab device and 
active scanning consume additional ~1.5W of energy and causing the network card to get really hot.

## SELinux

If you are using SELinux-enabled distro like Fedora, you need to go through the pain of install a new module with the 
permissions for the container to interact with D-Bus.

Save the following content as `switchbot-prometheus-exporter.te`:

```
module switchbot-prometheus-exporter 1.0;

require {
        type container_t;
        type system_dbusd_var_run_t;
        type system_dbusd_t;
        type bluetooth_t;
        class sock_file write;
        class unix_stream_socket connectto;
        class dbus send_msg;
}

#============= bluetooth_t ==============
allow bluetooth_t container_t:dbus send_msg;

#============= container_t ==============
allow container_t bluetooth_t:dbus send_msg;
allow container_t self:dbus send_msg;
allow container_t system_dbusd_var_run_t:sock_file write;
allow container_t system_dbusd_t:dbus send_msg;
allow container_t system_dbusd_t:unix_stream_socket connectto;

```

Then run:

```shell
checkmodule -M -m -o switchbot-prometheus-exporter.mod switchbot-prometheus-exporter.te
semodule_package -o switchbot-prometheus-exporter.pp -m switchbot-prometheus-exporter.mod
sudo semodule -i switchbot-prometheus-exporter.pp
```

> [!NOTE]  
> This might or might not introduce security risk for your system. Do it at your own risks!


## References / Credits

- https://github.com/louisblin/prometheus-switchbot-exporter
- https://github.com/OpenWonderLabs/node-switchbot/blob/bd44206094127456f2b9ec451fafaeb9a77bd787/src/device.ts#L2678
- https://github.com/OpenWonderLabs/SwitchBotAPI-BLE/blob/latest/devicetypes/meter.md

## License

```
Copyright © 2025 Dickson Leong

Permission is hereby granted, free of charge, to any person obtaining a copy of this software 
and associated documentation files (the “Software”), to deal in the Software without 
restriction, including without limitation the rights to use, copy, modify, merge, publish, 
distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the 
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or 
substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING 
BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND 
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, 
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```