#!/bin/bash
# hook to install tf demo workflow
echo "#### post start actions.sh hook happening"
workflow-install -w $GALAXY_ROOT/workflows/TF_example_wf.ga -g http://localhost:80 -a fakekey --publish_workflows
