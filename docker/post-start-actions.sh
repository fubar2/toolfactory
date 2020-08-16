#!/bin/bash
# hook to install tf demo workflow
echo "#### post start actions.sh hook happening"
chown $GALAXY_USER $GALAXY_ROOT/workflows/TF_example_wf.ga
workflow-install -w $GALAXY_ROOT/workflows/TF_example_wf.ga -g http://localhost -a fakekey --publish_workflows
