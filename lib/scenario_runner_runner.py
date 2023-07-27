#!/usr/bin/env python
#
# Copyright (c) 2020 Intel Corporation
#
"""
Executes scenario runner
"""
import os
from application_runner import ApplicationRunner, ApplicationStatus
from datetime import datetime, timedelta
try:
    import queue
except ImportError:
    import Queue as queue

class ScenarioRunnerRunner(ApplicationRunner):

    def __init__(self):
        self._application_result = None
        self._status_updates = queue.Queue()
        self._path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
        super(ScenarioRunnerRunner, self).__init__(self.status_updated, self.log_output, "ScenarioManager: Running scenario Demo")

    def status_updated(self, status):
        print("[SC STATUS] Status changed to {}".format(status))
        self._status_updates.put(status)

    def log_output(self, log):
        print("[SC]{}".format(log))

    def execute_scenario(self, scenario_file):
        self._status_updates = queue.Queue()

        cmdline = ["/usr/bin/python", "{}/carla-scenario-runner/scenario_runner.py".format(self._path), "--timeout",  "1000", "--openscenario", "{}/{}".format(self._path, scenario_file), "--waitForEgo"]
        result = self.execute(cmdline, env=os.environ)

        execution_time = datetime.now()
        if result is True:
            result = False
            while (datetime.now() - execution_time) < timedelta(seconds=16):
                try:
                    status = self._status_updates.get(block=True, timeout=1)
                    if status == ApplicationStatus.RUNNING:
                        result = True
                        break
                    elif status == ApplicationStatus.ERROR or status == ApplicationStatus.STOPPED:
                        break
                except queue.Empty:
                    pass
        return result
