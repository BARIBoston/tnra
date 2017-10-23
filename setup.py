#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name = "tnra",
    version = "0.3.0",
    license = "MIT",
    description = "Transportation Network Resilience Analytics platform by "
                  "the UIRLab at Northeastern University",
    packages = ["tnra"],
    install_requires = ["route_distances", "otpmanager", "pyzmq"],
    entry_points = {
        "console_scripts": [
            "tnra_server = tnra.server:start_server"
        ]
    }
)
