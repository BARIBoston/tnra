#!/usr/bin/env python3

import tnra

# Queue up a single route
client = tnra.Client()
client.enqueue(
    -71.089824, 42.337874, # origin longitude, latitude
    -71.116708, 42.372779, # destination longitude, latitude
    mode = "transit",      # optional: routing mode
    attributes = {         # optional: arbitrary route attributes
        "start_name": "northeastern university",
        "destination_name": "harvard university"
    }
)

# Open the output file
client.open_file("routes.json")

# Start the routing engine
import otpmanager
manager = otpmanager.OTPManager(
    "boston", -71.191155, 42.227926, -70.748802, 42.400819999999996,
    otp_path = "/home/leaf/otp-1.1.0-shaded.jar"
)
manager.start()

# This dict is passed as keyword arguments to the tnra.router.Router object
# initialization
tnra.start_routers({
    "otp_port": manager.port,
    "route_logging": False
})

# Stop the routing engine
manager.stop_otp()

# TNRA output files are not pure JSONs; instead, they have one JSON per row
import json
with open("routes.json", "r") as f:
    while True:
        line = f.readline()
        if (len(line) == 0):
            break
        else:
            print(
                json.dumps(
                    json.loads(line),
                    indent = 4
                )
            )
