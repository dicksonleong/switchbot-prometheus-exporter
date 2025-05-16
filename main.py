import asyncio
import logging
import time
from dataclasses import dataclass
from typing import override, Iterable

import click
from bleak import BleakScanner, BLEDevice, AdvertisementData
from bleak.backends.bluezdbus.scanner import BlueZDiscoveryFilters, BlueZScannerArgs
from prometheus_client import Metric, start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client.registry import Collector


SERVICE_UUID = "0000fd3d-0000-1000-8000-00805f9b34fb"


class SwitchBotCollector(Collector):
    def __init__(self, device_addr: str, scan_timeout: float):
        self._device_addr = device_addr
        self._scan_timeout = scan_timeout

    @override
    def collect(self) -> Iterable[Metric]:
        start_time = time.time()

        device_data = asyncio.run(find_device(address=self._device_addr, timeout=self._scan_timeout))
        if device_data is None:
            logging.warning(f"Device {self._device_addr} not found, used {(time.time() - start_time)}s")
            return

        end_time = time.time()

        device, ad_data = device_data
        logging.debug(f"Device {device.address} found, name: {device.name}, details: {device.details}")

        sensor_data = parse_service_data(ad_data)
        if sensor_data is None:
            logging.warning(f"Unable to parse service data from advertisement data: {ad_data}")
            return

        logging.info(f"Retrieved sensor data from {self._device_addr}: {sensor_data}, used {(end_time - start_time)}s")

        rssi = GaugeMetricFamily("switchbot_rssi", "Device received signal strength indicator (RSSI)",labels=["device"])
        rssi.add_metric([device.address], ad_data.rssi, end_time)
        yield rssi

        battery = GaugeMetricFamily("switchbot_battery", "Device battery percentage", labels=["device"])
        battery.add_metric([device.address], sensor_data.battery, end_time)
        yield battery

        humidity = GaugeMetricFamily("switchbot_humidity", "Humidity percentage measured by the device", labels=["device"])
        humidity.add_metric([device.address], sensor_data.humidity, end_time)
        yield humidity

        temperature = GaugeMetricFamily("switchbot_temperature", "Temperature in celsius measured by the device", labels=["device"])
        temperature.add_metric([device.address], sensor_data.temperature, end_time)
        yield temperature

    # noinspection PyMethodMayBeStatic
    def describe(self) -> Iterable[Metric]:
        rssi = GaugeMetricFamily("switchbot_rssi", "Device received signal strength indicator (RSSI)",labels=["device"])
        yield rssi

        battery = GaugeMetricFamily("switchbot_battery", "Device battery percentage", labels=["device"])
        yield battery

        humidity = GaugeMetricFamily("switchbot_humidity", "Humidity percentage measured by the device", labels=["device"])
        yield humidity

        temperature = GaugeMetricFamily("switchbot_temperature", "Temperature in celsius measured by the device", labels=["device"])
        yield temperature


@dataclass
class SensorData:
    battery: int
    temperature: float
    humidity: int


def configure_logging(debug: bool):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',level=level)


async def find_device(address: str, timeout: float) -> tuple[BLEDevice, AdvertisementData] | None:
    scanner_args = BlueZScannerArgs(filters=BlueZDiscoveryFilters(Transport="le", Pattern=address))
    async with BleakScanner(bluez=scanner_args) as scanner:
        try:
            async with asyncio.timeout(timeout):
                async for device, data in scanner.advertisement_data():
                    if device.address.upper() == address:
                        return device, data
                return None
        except asyncio.TimeoutError:
            return None


# https://github.com/OpenWonderLabs/node-switchbot/blob/bd44206094127456f2b9ec451fafaeb9a77bd787/src/device.ts#L2678
def parse_service_data(ad_data: AdvertisementData) -> SensorData | None:
    if SERVICE_UUID not in ad_data.service_data:
        return None

    service_data = ad_data.service_data[SERVICE_UUID]
    logging.debug("Service data: %s", service_data)

    byte2 = service_data[2]
    battery = byte2 & 0b01111111

    byte3 = service_data[3]
    byte4 = service_data[4]
    temp_sign = 1 if byte4 & 0b10000000 else -1
    temp_c = temp_sign * ((byte4 & 0b01111111) + (byte3 & 0b00001111) / 10)

    byte5 = service_data[5]
    humidity = byte5 & 0b01111111

    return SensorData(battery, temp_c, humidity)


@click.command()
@click.option("--device-addr", required=True, help="BLE device address", type=str)
@click.option("--metrics-port", default=8080, help="Prometheus metrics port", type=int, show_default=True)
@click.option("--scan-timeout", default=10, help="Timeout in seconds when scanning for BLE", type=int, show_default=True)
@click.option("--debug", help="Enable debug logging", is_flag=True)
def main(device_addr: str, metrics_port: int, scan_timeout: int, debug: bool):
    configure_logging(debug)

    REGISTRY.register(SwitchBotCollector(device_addr, scan_timeout))

    server, t = start_http_server(metrics_port)
    logging.info(f"Started Prometheus HTTP server on port {metrics_port}")

    server.serve_forever()


if __name__ == "__main__":
    main(auto_envvar_prefix="SWITCHBOT")
