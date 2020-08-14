# Galaxy - Toolshed
# Derived from bgruening rna and deeptools
# VERSION       0.2

FROM bgruening/galaxy-stable

MAINTAINER Ross Lazarus ross.lazarus@gmail.com

ENV GALAXY_CONFIG_BRAND ToolFactory


RUN add-tool-shed --url 'http://testtoolshed.g2.bx.psu.edu/' --name 'Test Tool Shed'

# Add toolfactory
ADD my_tool_list.yml $GALAXY_ROOT/tf_tool_list.yml

RUN install-tools $GALAXY_ROOT/tf_tool_list.yml && \
    /tool_deps/_conda/bin/conda clean --tarballs --yes
     > /dev/null && \
    rm /export/galaxy-central/ -rf

# place a file with that logic named post-start-actions.sh on the /export/ directory
ADD post-start-actions.sh /export/post-start-actions.sh
RUN chmod a+x /export/post-start-actions.sh

# Add Galaxy interactive tours
# ADD ./rna-workbench-tours/* $GALAXY_ROOT/config/plugins/tours/

# Add data library definition file
# ADD library_data.yaml $GALAXY_ROOT/library_data.yaml

# Add workflows to the Docker image

ADD TF_example_wf.ga $GALAXY_HOME/workflows/TF_example_wf.ga

# Mark folders as imported from the host.
VOLUME ["/export/"]


# Expose port 80 (webserver), 21 (FTP server), 8800 (Proxy)
EXPOSE :80
EXPOSE :21
EXPOSE :8800

# Autostart script that is invoked during container start
# CMD ["/usr/bin/startup"]
