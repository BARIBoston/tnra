#!/usr/bin/env python3

import json
import hashlib
import os
import pymongo
import random
import sys

import otpmanager
import route_distances
import tnra

SHELTER_INFO_PATH = "shelters.json"
DEFAULT_N_SCENARIOS = 200

def load_blockgroups(city, statefp = None):
    """ Load block group GeoJSON objects from Mongo

    Args:
        city: The name of the city to find block groups in
        statefp: The state FIPS code, to be used for differentiating cities
            with the same name that are in different states

    Returns:
        A list of GeoJSON features whose centroids lie within the queried city
    """

    tiger_2016 = pymongo.MongoClient()["tiger_2016"]

    query = {
        "properties.NAME": city
    }
    if (statefp):
        query["properties.STATEFP"] = str(statefp)

    city_boundaries = tiger_2016.cities.find_one(
        query
    )["geometry"]["geometries"][1]

    return list(tiger_2016.blockgroups.find({
        "geometry.geometries.0": {
            "$geoWithin": {
                "$geometry": city_boundaries
            }
        }
    }))

def create_scenarios(shelters, items_per_sample, n_scenarios = DEFAULT_N_SCENARIOS):
    """ Return a list of n scenario where each scenario is a unique combintion
    of items from the shelters array

    A scenario in this context is defined as a situation where only n
    shelters are accessible. This function returns up to a certain number of
    scenarios where, in each scenario, a unique combination of shelters are
    accessible, while all other shelters are inaccessible.

    Args:
        shelters: GeoJSON features of shelters
        items_per_sample: The number of items to include in each sample
        n_scenarios: The number of unique samples to return

    Returns:
        A list containing up to n_scenarios unique samples of shelters, where
        each sample is a list of size items_per_sample containing GeoJSON
        features of shelters. If the possible number of scenarios is less than
        n_scenarios, then all possible scenarios are returned.

    Raises
        AssertionError: The size of the space of possible unique combinations
            given the input parameters is less than the requested number of
            unique samples
    """

    n_possible_samples = len(shelters)**items_per_sample
    assert n_possible_samples > n_scenarios, \
           "The number of possible unique samples (%d) is less than the " \
           "requested number of samples (%d)" % (n_possible_samples, n_scenarios)

    samples = []
    sample_hashes = set()


    while (len(samples) < n_scenarios):
        new_sample = random.sample(shelters, items_per_sample)
        new_sample_hash = hashlib.md5(
            bytes(
                "".join([
                    shelter["properties"]["Name"] for shelter in new_sample
                ]),
                "utf-8"
            )
        ).hexdigest()

        if (not new_sample_hash in sample_hashes):
            sample_hashes.add(new_sample_hash)
            samples.append(new_sample)

    return samples

class Simulation(object):

    """ Class responsible for storing reusable information in memory, such as
    GeoJSONs, and running simulations

    Attributes:
        manager: An otpmanager.OTPManager object
        blockgroups: A list of block groups obtained from the UIRLab MongoDB
            shapefile database
        shelters: A list of GeoJSON points corresponding to shelters in Boston
        tnra_client: A tnra.Client() object
    """

    def __init__(self, shelters_path, city, statefp = None):
        """ Initializes Simulation class

        Args:
            shelters_path: The path to raw data obtained from
                http://boston.maps.arcgis.com/apps/LocalPerspective/index.html?appid=1fe94c3d1ae24527b3bd720371531bac
            city: The city to query the MongoDB for blockgroups
            statefp: The state FIPS code to query MongoDB for a city
        """

        self.manager = otpmanager.OTPManager(
            "boston", -71.191155, 42.227926, -70.748802, 42.400819999999996,
            otp_path = "/home/uirlab/otp-1.1.0-shaded.jar"
        )

        print("Loading block groups from Mongo")
        self.blockgroups = load_blockgroups("Boston", "25")
        for blockgroup in self.blockgroups:
            del(blockgroup["_id"])

        print("Loading shelters")
        with open(shelters_path, "r") as f:
            self.shelters = json.load(f)["features"]

        print("Initializing TNRA client")
        self.tnra_client = tnra.Client()

    def run(self, items_per_sample, mode = "walk",
            n_scenarios = DEFAULT_N_SCENARIOS):
        """ Run a simulation

        One run includes running n scenarios where n is up to n_scenarios
        scenarios returned by the create_scenarios function. See the
        documentation of create_scenarios for more information.

        Args:
            items_per_sample: The number of shelters to include in each
                scenario
            mode: The mode of transportation to use
            n_scenarios: The maximum number of scenarios to run
        """

        print("Creating scenarios")
        try:
            scenarios = create_scenarios(self.shelters, items_per_sample,
                                         n_scenarios)
        except AssertionError:
            print("Warning: possible number of unique shelter combinations is "
                  "less than the number of requested combinations")
            scenarios = [[x] for x in self.shelters]

        print("Scenarios: %d; block groups: %d; shelters: %d" % (
            len(scenarios), len(self.blockgroups), len(self.shelters)
        ))

        print("Enqueueing %d routes" % (
            len(scenarios) * len(self.blockgroups) * len(self.shelters)
        ))
        i = 0
        for scenario in scenarios:
            for blockgroup in self.blockgroups:
                blockgroup_coords = blockgroup["geometry"]["geometries"][0]["coordinates"]
                for shelter in self.shelters:
                    shelter_coords = shelter["geometry"]["coordinates"]

                    self.tnra_client.enqueue(
                        *tuple(blockgroup_coords + shelter_coords),
                        mode = mode,
                        attributes = {
                            "blockgroup_geoid": blockgroup["properties"]["GEOID"],
                            "shelter_objectid": shelter["properties"]["OBJECTID"]
                        }
                    )

                    i += 1
                    sys.stdout.write("\r%d" % i)
                    sys.stdout.flush()

        print("")
        with open("out.json", "w") as f:
            json.dump(scenarios, f, indent = 4)

        print("Setting up output")
        output_directory = ("%d_shelters" % items_per_sample)
        if (not os.path.isdir(output_directory)):
            os.makedirs(output_directory)
        with open("%s/scenarios_%s.json" % (output_directory, mode), "w") as f:
            json.dump(scenarios, f, indent = 4)
        self.tnra_client.open_file("%s/%s/%routes_%s.json" % (
            os.path.realpath("."), output_directory, mode
        ))

        print("Initializing OpenTripPlanner")
        self.manager.start()

        print("Running simulation")
        tnra.start_routers({
            "router": route_distances.OTPDistances,
            "kwargs": {
                "entrypoint": "localhost:%d" % self.manager.port
            },
            "route_logging": False
        })

        self.manager.stop_otp()

def main(shelter_info_path = SHELTER_INFO_PATH, city = "Boston"):
    sim = Simulation(shelter_info_path, city)

    #for i in range(1, len(sim.shelters) - 1):
    #    for mode in ["walk", "drive", "transit"]:
    #        sim.run(i, mode)

    sim.run(1, "drive")

if (__name__ == "__main__"):
    main()
