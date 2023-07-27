#!/bin/bash
# kill remaining processes
PID_SCENARIO_RUNNER=$(pgrep -f 'scenario_runner.py')
PID_MANUAL_CONTROL=$(pgrep -f 'manual_control_rss_demo.py')
for pid_to_kill in $PID_SCENARIO_RUNNER $PID_MANUAL_CONTROL; do
  # echo $pid_to_kill
  # don't kill ourselves or our parent
  if [[ $pid_to_kill != $$ && $pid_to_kill != $PPID ]]; then
    echo "killing $pid_to_kill"
    kill -9 $pid_to_kill
  fi
done
DEMO_ROOT=$(dirname $(readlink -f $0))
eval PYTHONPATH=${DEMO_ROOT}/lib:${DEMO_ROOT}/dialogs/:${PYTHONPATH} $@
