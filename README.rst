Transportation Network Resilience Analytics platform
====================================================

A platform for large scale, distributed routing applications based in Python
and using OpenTripPlanner, by the UIRLab at Northeastern University (WIP)

Dependencies on Other UIRLab Projects
-------------------------------------

These must be installed before using the TNRA platform.

`route_distances <https://github.com/ercas/route_distances>`_: A library that
simplifies interfacing with multiple different routing services.

`otpmanager <https://github.com/ercas/otp_manager>`_: A library that provides
Python procedures for programatically starting up and monitoring
OpenTripPlanner, which is the routing engine used by the TNRA platform.

Installation
------------

::

    git clone https://github.com/BARIBoston/tnra
    sudo pip3 install ./tnra/

..

Usage - Single Computer / Main Cluster Node
-------------------------------------------

1. Start the TNRA server

::

    tnra_server

..

2. Connect to the server using the tnra.Client object and start queueing routes

.. code-block:: python

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

..

3. Start using the TNRA platform

.. code-block:: python

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
    import route_distances
    tnra.start_routers({
        "router": route_distances.OTPDistances,
        "kwargs": {
            "entrypoint": "localhost:%d" % manager.port
        },
        "route_logging": False
    })

    # Stop the routing engine
    manager.stop_otp()

..

4. Analyze results


.. code-block:: python

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
                        json.load(f),
                        indent = 4
                    )
                )

..

The above code is available as an example script, `example.py`.

Usage - Cluster Worker Node
---------------------------

TODO

TODO
----

* Custom JSON reader class to handle TNRA JSON format - TNRA outputs JSONs that
  are plaintext files of one JSON on each line, to allow for lazy loading of
  lines which is necessary due to potentially massive output files
* Port worker node connection code over from Redis to TNRA server
* Possible alternative user interfaces (e.g. Flask)
