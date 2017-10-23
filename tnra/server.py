#!/usr/bin/env python3

import json
import pickle
import threading
import zlib
import zmq

DEFAULT_PORT = 5555
DEFAULT_TIMEOUT_MS = 5000

COMMANDS = {
    "exit": 10,
    "echo": 11,
    "ping": 12,

    "enqueue": 20,
    "queue_pop": 21,
    "queue_size": 22,
    "queue_flush": 23,

    "open_file": 30,
    "close_file": 31,
    "write_to_disk": 32,
    "save_queue": 33,
    "load_queue": 34,

    "get_var": 40,
    "set_var": 41,
    "save_vars": 42,
    "load_vars": 43
}

RESPONSES = {
    "ok": 10,
    "notok": 11,

    "queue_empty": 20
}

def parse_body(response):
    """ Return the body of a message only if the response is OK, or True if
    there is no body"""

    if (response["rsp"] == RESPONSES["ok"]):
        if ("body" in response):
            return response["body"]
        else:
            return True
    else:
        return None

class TimeoutError(IOError):
    pass

class Server(threading.Thread):

    """ Implementation of lightweight FILO queue server and endpoint for
    data dumping using ZeroMQ """

    def __init__(self, port = DEFAULT_PORT):
        threading.Thread.__init__(self)

        self._file = None

        self._context = zmq.Context()

        self._socket = self._context.socket(zmq.REP)
        self._socket.bind("tcp://*:%d" % port)
        self._socket.setsockopt(zmq.LINGER, 0)

        self.port = port
        self.queue = []
        self.vars = {}

    def send_rsp(self, message):
        """ Wrapper for zmq.Context.socket.send

        Args:
            message: The message to send
        """

        assert "rsp" in message, "Poorly formatted response"
        self._socket.send(pickle.dumps(message))

    def recv_cmd(self):
        """ Wrapper for zmq.Context.socket.recv

        Returns:
            The received message
        """

        message = pickle.loads(self._socket.recv())
        assert "cmd" in message, "Poorly formatted command"
        return message

    def run(self):
        while True:
            message = self.recv_cmd()

            ## 1X ##############################################################
            if (message["cmd"] == COMMANDS["exit"]):
                if (self._file is not None):
                    self._file.close()
                break

            elif (message["cmd"] == COMMANDS["echo"]):
                print(message["body"])
                self.send_rsp({"rsp": RESPONSES["ok"]})

            elif (message["cmd"] == COMMANDS["ping"]):
                self.send_rsp({"rsp": RESPONSES["ok"]})

            ## 2X ##############################################################
            elif (message["cmd"] == COMMANDS["enqueue"]):
                self.queue.append(zlib.compress(pickle.dumps(message["body"])))
                self.send_rsp({"rsp": RESPONSES["ok"]})

            elif (message["cmd"] == COMMANDS["queue_pop"]):
                if (len(self.queue) > 0):
                    self.send_rsp({
                        "rsp": RESPONSES["ok"],
                        "body": pickle.loads(zlib.decompress(self.queue.pop()))
                    })
                else:
                    self.send_rsp({
                        "rsp": RESPONSES["queue_empty"],
                    })

            elif (message["cmd"] == COMMANDS["queue_size"]):
                self.send_rsp({
                    "rsp": RESPONSES["ok"],
                    "body": len(self.queue)
                })

            elif (message["cmd"] == COMMANDS["queue_flush"]):
                self.queue = []
                self.send_rsp({"rsp": RESPONSES["ok"]})

            ## 3X ##############################################################
            elif (message["cmd"] == COMMANDS["open_file"]):
                if (self._file):
                    self._file.close()
                self._file = open(
                    message["body"]["filename"], message["body"]["mode"]
                )
                self.send_rsp({"rsp": RESPONSES["ok"]})

            elif (message["cmd"] == COMMANDS["close_file"]):
                assert self._file is not None
                self._file.close()
                self.send_rsp({"rsp": RESPONSES["ok"]})

            elif (message["cmd"] == COMMANDS["write_to_disk"]):
                assert self._file is not None
                self._file.write("%s\n" % message["body"])
                self.send_rsp({"rsp": RESPONSES["ok"]})

            elif (message["cmd"] == COMMANDS["save_queue"]):
                with open(message["body"]["filename"], "w") as f:
                    for item in queue:
                        f.write("%s\n" % pickle.loads(zlib.decompress(item)))
                self.send_rsp({"rsp": RESPONSES["ok"]})

            elif (message["cmd"] == COMMANDS["load_queue"]):
                with open(message["body"]["filename"], "r") as f:
                    while True:
                        item = f.readline()
                        if (len(item) == 0):
                            break
                        else:
                            self.queue.append(
                                zlib.compress(pickle.dumps(message["body"]))
                            )
                self.send_rsp({"rsp": RESPONSES["ok"]})

            ## 4X ##############################################################
            elif (message["cmd"] == COMMANDS["get_var"]):
                if message["body"]["key"] in self.vars:
                    self.send_rsp({
                        "rsp": RESPONSES["ok"],
                        "body": self.vars[message["body"]["key"]]
                    })
                else:
                    self.send_rsp({
                        "rsp": RESPONSES["ok"],
                        "body": None
                    })

            elif (message["cmd"] == COMMANDS["set_var"]):
                self.vars[message["body"]["key"]] = message["body"]["value"]
                self.send_rsp({"rsp": RESPONSES["ok"]})

            elif (message["cmd"] == COMMANDS["save_vars"]):
                with open(message["body"]["filename"], "w") as f:
                    json.dump(self.vars, f, indent = 4)
                self.send_rsp({"rsp": RESPONSES["ok"]})

            elif (message["cmd"] == COMMANDS["load_vars"]):
                with open(message["body"]["filename"], "r") as f:
                    self.vars = json.load(f)
                self.send_rsp({"rsp": RESPONSES["ok"]})

class Client(object):

    """ Implementation of lightweight ZeroMQ FILO queue client """

    def __init__(self, host = "localhost", port = DEFAULT_PORT):
        self._context = zmq.Context()

        self._socket = self._context.socket(zmq.REQ)
        self._socket.connect("tcp://%s:%d" % (host, port))
        self._socket.setsockopt(zmq.LINGER, 0)

        self._poller = zmq.Poller()
        self._poller.register(self._socket, zmq.POLLIN)

        self.port = port

    def send_cmd(self, message):
        """ Wrapper for zmq.Context.socket.send

        Args:
            message: The message to send
        """

        assert "cmd" in message, "Poorly formatted command"
        self._socket.send(pickle.dumps(message))

    def recv_rsp(self):
        """ Wrapper for zmq.Context.socket.recv

        Returns:
            The received message
        """

        if (self._poller.poll(DEFAULT_TIMEOUT_MS)):
            message = pickle.loads(self._socket.recv())
            assert "rsp" in message, "Poorly formatted response"
            return message
        else:
            raise TimeoutError

    ## 1X ######################################################################
    def exit(self):
        self.send_cmd({"cmd": COMMANDS["exit"]})
        return True

    def echo(self, message):
        self.send_cmd({
            "cmd": COMMANDS["echo"],
            "body": message
        })
        return parse_body(self.recv_rsp())

    def ping(self):
        self.send_cmd({"cmd": COMMANDS["ping"]})
        return parse_body(self.recv_rsp())

    ## 2X ######################################################################
    def enqueue(self, *args, **kwargs):
        self.send_cmd({
            "cmd": COMMANDS["enqueue"],
            "body": (args, kwargs)
        })
        return parse_body(self.recv_rsp())

    def queue_pop(self):
        self.send_cmd({"cmd": COMMANDS["queue_pop"]})
        return parse_body(self.recv_rsp())

    def queue_size(self):
        self.send_cmd({"cmd": COMMANDS["queue_size"]})
        return parse_body(self.recv_rsp())

    def queue_flush(self):
        self.send_cmd({"cmd": COMMANDS["queue_flush"]})
        return parse_body(self.recv_rsp())

    ## 3X ######################################################################
    def close_file(self):
        self.send_cmd({"cmd": COMMANDS["close_file"]})
        return parse_body(self.recv_rsp())

    def open_file(self, filename, mode = "w"):
        self.send_cmd({
            "cmd": COMMANDS["open_file"],
            "body": {
                "filename": filename,
                "mode": mode
            }
        })
        return parse_body(self.recv_rsp())

    def write_to_disk(self, body):
        self.send_cmd({
            "cmd": COMMANDS["write_to_disk"],
            "body": json.dumps(body)
        })
        return parse_body(self.recv_rsp())

    def save_queue(self, filename = "queue.json"):
        self.send_cmd({
            "cmd": COMMANDS["save_queue"],
            "body": {
                "filename": filename
            }
        })
        return parse_body(self.recv_rsp())

    def load_queue(self, filename):
        self.send_cmd({
            "cmd": COMMANDS["load_queue"],
            "body": {
                "filename": filename
            }
        })
        return parse_body(self.recv_rsp())

    ## 4X ######################################################################
    def get_var(self, key):
        self.send_cmd({
            "cmd": COMMANDS["get_var"],
            "body": {
                "key": key
            }
        })
        return parse_body(self.recv_rsp())

    def set_var(self, key, value):
        self.send_cmd({
            "cmd": COMMANDS["set_var"],
            "body": {
                "key": key,
                "value": value
            }
        })
        return parse_body(self.recv_rsp())

    def set(self, key, value):
        self.send_cmd({
            "cmd": COMMANDS["get_var"],
            "body": {
                "key": key,
                "value": value
            }
        })
        return parse_body(self.recv_rsp())

    def save_vars(self, filename = "vars.json"):
        self.send_cmd({
            "cmd": COMMANDS["save_vars"],
            "body": {
                "filename": filename
            }
        })
        return parse_body(self.recv_rsp())

    def load_vars(self, filename):
        self.send_cmd({
            "cmd": COMMANDS["load_vars"],
            "body": {
                "filename": filename
            }
        })
        return parse_body(self.recv_rsp())

def start_server():
    server = Server()
    print("Starting TNRA server...")
    server.start()
    server.join()
