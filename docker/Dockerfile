# Galaxy - Toolshed
# Derived from bgruening deeptools
# VERSION       0.2

FROM bgruening/galaxy-stable

MAINTAINER Ross Lazarus ross.lazarus@gmail.com

ENV GALAXY_CONFIG_BRAND ToolFactory
# The following two lines are optional and can be given during runtime
# with the -e http_proxy='http://yourproxyIP:8080' parameter
#ENV http_proxy 'http://yourproxyIP:8080'
#ENV https_proxy 'http://yourproxyIP:8080'

WORKDIR /galaxy-central

RUN add-tool-shed --url 'http://testtoolshed.g2.bx.psu.edu/' --name 'Test Tool Shed'


# Add toolfactory
ADD my_tool_list.yml $GALAXY_ROOT/my_tool_list.yml
RUN install-tools $GALAXY_ROOT/my_tool_list.yml

RUN mkdir -p $GALAXY_ROOT/scripts && mkdir -p $GALAXY_ROOT/scripts/api
ADD api $GALAXY_ROOT/scripts/api/
ADD TF_example_wf.ga $GALAXY_ROOT/workflows/TF_example_wf.ga

# place a file with that logic named post-start-actions.sh on the /export/ directory
RUN mkdir -p /export
ADD post-start-actions.sh /export
RUN chmod a+x /export/post-start-actions.sh

# Mark folders as imported from the host.
VOLUME ["/export/", "/data/", "/var/lib/docker"]

# Expose port 80 (webserver), 21 (FTP server), 8800 (Proxy)
EXPOSE :80
EXPOSE :21
EXPOSE :8800

# Autostart script that is invoked during container start
CMD ["/usr/bin/startup"]
