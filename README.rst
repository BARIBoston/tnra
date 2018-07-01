Transportation Network Resilience Analytics platform
====================================================

.. image:: https://zenodo.org/badge/104003645.svg
   :target: https://zenodo.org/badge/latestdoi/104003645

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

Usage - Server / Main Node
--------------------------

The TNRA server is responsible for distributing work to clients and writing
incoming data to a file on the disk. The TNRA server can be started with the
following command after installation:

::

    tnra_server

..

Usage - Clients / Worker Nodes
------------------------------

Worker nodes are responsible for starting up their own routing engines,
requesting jobs from the main node, doing work, and sending the results back to
the main node. By default, worker nodes will soak up all cores available on the
machine on which they are run, but this can be toggled with the `threads`
argument of `tnra.start_routers`.

1. Connect to the server using the tnra.Client object and start enqueueing
   routes, if necessary

.. code-block:: python

    import tnra

    # Queue up a single route
    client = tnra.Client() # If on the main node, the host can be ommitted
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

2. Start using the TNRA platform

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

3. Analyze results


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

TODO
----

* Custom JSON reader class to handle TNRA JSON format - TNRA outputs JSONs that
  are plaintext files of one JSON on each line, to allow for lazy loading of
  lines which is necessary due to potentially massive output files
* Port worker node connection code over from Redis to TNRA server
* Possible alternative user interfaces (e.g. Flask)
