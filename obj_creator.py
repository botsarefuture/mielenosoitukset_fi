import time
import random
import os
import struct
import binascii
from datetime import datetime


class ObjectId:
    # Initialize a class variable for the counter and set it to a random 3-byte integer
    _counter = random.randint(0, 0xFFFFFF)

    def __init__(self, value=None):
        raise PendingDeprecationWarning("This will be Depraced in V2! Use bson.objectid.ObjectId() instead!")

        if isinstance(
            value, int
        ):  # If the input is an integer, treat it as a timestamp
            timestamp = value
            self._random_value = ObjectId._generate_random_value()
            self._counter = ObjectId._generate_counter()
        elif isinstance(value, str):  # If the input is a hexadecimal string, parse it
            self._id = bytes.fromhex(value)
            return
        else:
            timestamp = int(time.time())
            self._random_value = ObjectId._generate_random_value()
            self._counter = ObjectId._generate_counter()

        # Construct the 12-byte ObjectId
        self._id = (
            struct.pack(">I", timestamp)
            + self._random_value
            + struct.pack(">I", self._counter)[1:]
        )

    @staticmethod
    def _generate_random_value():
        # 5-byte random value unique to the machine and process
        return os.urandom(5)

    @staticmethod
    def _generate_counter():
        # Increment the counter and mask to get only the last 3 bytes
        ObjectId._counter = (ObjectId._counter + 1) & 0xFFFFFF
        return ObjectId._counter

    def getTimestamp(self):
        # Extract and return the timestamp part of the ObjectId as a datetime object
        timestamp = struct.unpack(">I", self._id[:4])[0]
        return datetime.fromtimestamp(timestamp)

    def __str__(self):
        # Return the ObjectId as a hexadecimal string
        return binascii.hexlify(self._id).decode("utf-8")

    def __repr__(self):
        return f'ObjectId("{self.__str__()}")'
