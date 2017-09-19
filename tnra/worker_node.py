#!/usr/bin/env python3
# responsible for calculations
# BROKEN - assumes old Redis server

import atexit
import os
import subprocess
import time

import otpmanager

from . import router, server

CONFIG = configparser.ConfigParser()
CONFIG.read("config.ini")

OTP_PATH = CONFIG["otp"]["path"]

PORT = CONFIG["databases"]["queue_port"]

def connect_to_main_node(hostame):
    """ Attempts to connect to the server on the main node

    Args:
        hostname: The hostname of the main node

    Returns:
        True if a connection could be made; False if not
    """
    print("setting up SSH TCP tunnel for port %d" % PORT)

    args = [
        "ssh",
        "-fNL",
        "%d:localhost:%d" % (PORT, PORT),
        hostname
    ]
    print("Calling %s" % " ".join(args))
    ssh_thread = subprocess.call(args)

    try:
        atexit.register(ssh_thread.kill)
    except AttributeError:
        print("Could not open SSH tunnel; continuing anyway")
        print("If this is running on the same server as the main server, "
              "this message can be safely ignored.")

    time.sleep(2)

    for i in range(connect_to_main_node_ATTEMPTS):
        try:
            server.Client().queue_size()
            return True
        except redis.exceptions.ConnectionError as err:
            if (i != connect_to_main_node_ATTEMPTS):
                print("Could not connect to Redis; trying again in 2 seconds")
        time.sleep(2)

    try:
        ssh_thread.kill()
    except AttributeError:
        pass
    return False

if (__name__ == "__main__"):
    import optparse
    parser = optparse.OptionParser()
    parser.add_option("-c", "--city", dest = "city",
                      help = "City whose graph should be loaded",
                      metavar = "CITY")
    parser.add_option("-H", "--hostname", dest = "hostname",
                      help = "The hostname of the main server containing the "
                             "running Redis instance. You can also specify "
                             "the user by supplying user@hostname instead of "
                             "just the hostname, as in the ssh command")
    (options, args) = parser.parse_args()

    router_kwargs = vars(options)

    if (None in router_kwargs.values()):
        print("All options are mandatory\n")
        parser.print_help()
    else:
        hostname = router_kwargs.pop("hostname")
        city = router_kwargs.pop("city")

        if (connect_to_main_node(hostname)):
            print("Starting node")

            # Here, we use (0, 0, 0, 0) as the bounding box because we assume
            # that the graph is already pre-generated, so the bounding box
            # does not matter
            manager = otpmanager.OTPManager(
                city, 0, 0, 0, 0, otp_path = OTP_PATH
            )
            manager.start()
            time.sleep(2)

            router_kwargs = {
                "otp_port": manager.port
            }
            router.start_routers(
                router_kwargs
            )

            manager.stop()

            print("Node finished")

        else:
            print("Failed to connect to Redis")
