#!/usr/bin/env python3
# continuously pulls from the main node's queue and returns calculations

import datetime
import json
import multiprocessing
import os
import time

import route_distances

from . import server

MAX_THREADS = multiprocessing.cpu_count()

DEPARTURE_WEEKDAY = 3 # day of week to standardize departures to
DEPARTURE_HOUR = 11   # hour of day to stanrardize departures to

ROUTE_LOGGING = True
ROUTE_LOG_PATH = "routing_logs.json"

VERBOSE = True

HOURS_IN_DAY = 60 * 60 * 24

def next_weekday(datetime_now = None, desired_weekday = 3):
    """ Find the date of the next desied week day

    1 = monday; 7 = sunday

    Args:
        desired_weekday: The week day to be used

    Returns:
        A datetime.datetime object corresponding to the next date with the
        desired weekday
    """

    if (datetime_now is None):
        datetime_now = datetime.datetime.now()
    now_weekday = datetime_now.isoweekday()

    if (now_weekday == desired_weekday):
        return datetime_now
    elif (now_weekday < desired_weekday):
        timestamp_delta = (desired_weekday - now_weekday) * HOURS_IN_DAY
    elif (now_weekday > desired_weekday):
        timestamp_delta = (desired_weekday + 7 - now_weekday) * HOURS_IN_DAY
    return datetime.datetime.fromtimestamp(
        datetime_now.timestamp() + timestamp_delta
    )

class Router(object):

    def __init__(self, otp_port, route_logging = ROUTE_LOGGING,
                 route_log_path = ROUTE_LOG_PATH):
        """ Initializes Router object

        Args:
            otp_port: The port that OpenTripPlanner accepts HTTP requests on
            route_logging: Whether or not to log all routes
            route_log_pah: The path to log all routes to, if route_logging is True
        """

        self.client = server.Client()
        self.calculator = route_distances.OTPDistances("localhost:%d" % otp_port)
        self.logging = route_logging
        self.route_log_path = route_log_path

    def route(self, origin_x, origin_y, dest_x, dest_y, mode,
              weekday = DEPARTURE_WEEKDAY, hour = DEPARTURE_HOUR,
              attributes = None):
        """ Calculate a route between two block groups

        Args:
            origin_x, origin_y, dest_x, dest_y: Routing arguments
            mode: The route_distances mode of transportation to use
            weekday: The desired ISO weekday of departure
            hour: The desired ISO hour of departure
            attributes: Data to be added to the route
        """

        output = []
        output.append("%s Attributes: %s" % (mode, attributes))

        departure_datetime = next_weekday(desired_weekday = DEPARTURE_WEEKDAY)
        departure_time = datetime.datetime(
            departure_datetime.year,
            departure_datetime.month,
            departure_datetime.day,
            DEPARTURE_HOUR
        )
        result = self.calculator.distance(
            origin_x,
            origin_y,
            dest_x,
            dest_y,
            mode,
            departure_time = departure_time
        )

        success = 0

        # no further intervention needed
        if (result):
            success = 1

            output.append("%s: => Duration: %f" % (mode, result["duration"]))
            output.append("%s: => Distance: %f" % (mode, result["distance"]))
            self.client.write_to_disk({
                "response": result["response"],
                "attributes": attributes
            })

        # try to seek for a valid route
        # or have a different script overwrite the queue's origin/dest
        else:
            # TODO
            pass

        if (success == 0):
            output.append("%s: No route" % mode)

        if (self.logging):
            with open(self.route_log_path, "a") as f:
                f.write(
                    json.dumps({
                        "time": time.time(),
                        "success": success,
                        "origin_x": origin_x, "origin_y": origin_y,
                        "dest_x": dest_x, "dest_y": dest_y,
                        "departure_time": departure_time.timestamp(),
                        "attributes": attributes
                    })
                )
                f.write("\n")


        if (VERBOSE):
            print("\n".join(output))

    def main(self):
        """ Router main loop

        Continuously pulls self.route kwargs from the Redis queue and
        calculates routes until the queue is empty
        """

        next_ = self.client.queue_pop()
        while (next_):
            self.route(*next_[0], **next_[1])
            next_ = self.client.queue_pop()

def init_router(router_kwargs):
    """ Wrapper function for the initialization of a Router object

    Args:
        router_kwargs: A dictionary of kwargs to be passed to Router.__init__
    """

    Router(**router_kwargs).main()

def start_routers(router_kwargs, threads = MAX_THREADS):
    """ Wrapper function for starting multiple routers

    Args:
        router_kwargs: A dictionary of kwargs to be passed to Router.__init__
        threads: The number of threads to start
    """

    pool = multiprocessing.Pool(threads)
    pool.map(
        init_router,
        [router_kwargs] * threads
    )
    pool.close()
    pool.join()
