#!/usr/bin/env python3
import argparse
import copy
import faulthandler
import json
import logging
import os
import subprocess
import sys
import threading
import time
import yaml
from collections import namedtuple
from datetime import datetime, timedelta
from enum import IntEnum
from time import sleep
from lib.victron_ble.victron_gatt_ble import manager

with open("config-new.yml", 'r') as ymlfile:
    config = yaml.full_load(ymlfile)


logger_format = '[%(levelname)-7s] (%(asctime)s) %(filename)s::%(lineno)d %(message)s'
logging.basicConfig(level=logging.INFO,
                    format=logger_format,
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename=f"main.log")
logger = logging.getLogger()

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter(logger_format)
handler.setFormatter(formatter)
logger.addHandler(handler)


def output_syslog(device, category, value):
    #print(f"{device}|{category}:{value}", file=sys.stderr)
    subprocess.run(
        [
            "/usr/bin/logger",
            f"--id={os.getpid()}",
            "-t",
            "victron",
            f"{device}|{category}:{value}",
        ]
    )


def output_mqtt(device, category, value):
    global client

    if value == "":
        client.publish(f"victron/{device}", category)
    else:
        if type(value) is dict:
            data = json.dumps(value)
        else:
            data = '{"payload": ' + value + ' }'
        client.publish(f"victron/{device}/{category}", data)


def get_helper_string_device(devices):
    return_string = ""
    for count, device in enumerate(devices):
        return_string += f"{count}: {device['name']} | "
    return return_string

if __name__ == "__main__":
    ## REMOVE LATER, ONLY FOR SEGFAULT DEBUGGING
    faulthandler.enable(all_threads=True)

    parser = argparse.ArgumentParser(description="Victron Reader (Bluetooth or Serial) \n\n"
                                                 "Current supported devices:\n"
                                                 "  Full: \n" 
                                                 "  Partial: \n"
                                                 "    - Smart Shunt (Bluetooth)\n"
                                                 "Default behavior:\n"
                                                 "  1. It will connect to all known or given device\n"
                                                 "  2. Collect and log data summary as defined at the config file\n"
                                                 "  3. Disconnect",
                                     formatter_class=argparse.RawTextHelpFormatter)
    group01 = parser.add_argument_group()
    group01.add_argument("--debug", action="store_true", help="Set log level to debug")
    group01.add_argument("--quiet", action="store_true", help="Set log level to error")

    group03 = parser.add_argument_group()
    group03.add_argument(
        "-d",
        "--device",
        metavar="NUM",
        type=int,
        help=get_helper_string_device(config['devices']),
        required=True,
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        handler.setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
        handler.setLevel(logging.ERROR)

    #config['keep_connected'] = args.keep_connected
    #config['direct_disconnect'] = args.direct_disconnect

    if config['logger'] == 'mqtt':
        import paho.mqtt.client as mqtt

        client = mqtt.Client()
        client.connect(config['mqtt']['host'], config['mqtt']['port'], 60)
        client.loop_start()

        output = output_mqtt
    elif config['logger'] == 'syslog':
        output = output_syslog

    bt = False

    # Build device list with all devices or just the given by commandline
    if args.device is not None:
        devices_config = [config['devices'][args.device]]
    else:
        devices_config = config['devices']

    for count, device_config in enumerate(devices_config):
        victron_devices = []

        if device_config['protocol'] == 'bluetooth-ble':
            from lib.victron_ble.victron import VictronBLE
            v = VictronBLE(device_config, output)
            v.read_once()
            bt = True

    if bt:
        logger.info("Gatt manager event loop starting...")
        manager.run()


