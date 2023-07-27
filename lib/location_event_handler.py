#!/usr/bin/env python

# handle events depending on location
#

import math
class LocationEventHandler(object):

    def __init__(self):
        self._registered_events = []

    def register_event(self, pos, max_distance, id, fct):
        event = {}
        event["pos"] = pos
        event["distance"] = max_distance
        event["id"] = id
        event["fct"] = fct
        event["active"] = False
        self._registered_events.append(event)

    def retrigger(self, player, id):
        for event in self._registered_events:
            if event["id"] == id:
                distance = self.calculate_distance((player.get_transform().location.x, player.get_transform().location.y), event["pos"])
                if distance < event["distance"] and not event["active"]:
                    event["active"] = True
                    print("Event {} gets active.".format(event["id"]))
                    event["fct"](event["id"], True)
                elif event["active"] and distance > event["distance"]:
                    event["active"] = False
                    print("Event {} gets inactive.".format(event["id"]))
                    event["fct"](event["id"], False)


    def calculate_distance(self, pos1, pos2):
        return math.sqrt((pos1[0]-pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def tick(self, player):
        for event in self._registered_events:
            distance = self.calculate_distance((player.get_transform().location.x, player.get_transform().location.y), event["pos"])
            if distance < event["distance"] and not event["active"]:
                event["active"] = True
                print("Event {} gets active.".format(event["id"]))
                event["fct"](event["id"], True)
            elif event["active"] and distance > event["distance"]:
                event["active"] = False
                print("Event {} gets inactive.".format(event["id"]))
                event["fct"](event["id"], False)
