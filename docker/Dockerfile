# Galaxy - Toolshed Docker image
# Derived from bgruening stable galaxy 
# VERSION       0.2
# patches startup so the below will install a workflow dropped into $GALAXY_ROOT/workflows
# use docker run -p 8080:80  -d -e GALAXY_AUTO_UPDATE_WORKFLOWS=/galaxy-central/workflows/TF_sample_wf.ga -v /home/ubuntu/galaxy_storage/:/export/  toolfactory
FROM bgruening/galaxy-stable
MAINTAINER Ross Lazarus ross.lazarus@gmail.com

ENV GALAXY_CONFIG_BRAND=ToolFactory
ENV GALAXY_LOGGING="full"

# RUN apt-get update -y && apt-get install -y build-essential gcc apt-utils
# needed for planemo build

RUN /galaxy_venv/bin/python -m pip install --upgrade pip
# RUN /galaxy_venv/bin/python -m pip install planemo

# RUN add-tool-shed --url 'http://testtoolshed.g2.bx.psu.edu/' --name 'Test Tool Shed'
ADD my_tool_list.yml $GALAXY_ROOT/config/toolfactory_tools.yaml
ENV GALAXY_AUTO_UPDATE_TOOLS=$GALAXY_ROOT/config/toolfactory_tools.yaml

# Add workflows to the Docker image
RUN mkdir -p $GALAXY_ROOT/workflows
ADD TF_example_wf.ga $GALAXY_ROOT/workflows/TF_example_wf.ga
ADD post-start-actions.sh /export/post-start-actions.sh
RUN chmod a+xr /export/post-start-actions.sh \
 && chmod a+xr $GALAXY_ROOT/workflows/TF_example_wf.ga 

# Add Galaxy interactive tours
# ADD ./rna-workbench-tours/* $GALAXY_ROOT/config/plugins/tours/
# Add data library definition file
# ADD library_data.yaml $GALAXY_ROOT/library_data.yaml
# cleanup dance
RUN apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && rm -rf ~/.cache/ \
    && find $GALAXY_ROOT/ -name '*.pyc' -delete | true \
    && find /usr/lib/ -name '*.pyc' -delete | true \
    && find /var/log/ -name '*.log' -delete | true \
    && find $GALAXY_VIRTUAL_ENV -name '*.pyc' -delete | true \
    && rm -rf /tmp/* /root/.cache/ /var/cache/* $GALAXY_ROOT/client/node_modules/ $GALAXY_VIRTUAL_ENV/src/ /home/galaxy/.cache/ /home/galaxy/.npm
ENV GALAXY_DEFAULT_ADMIN_USER=''
VOLUME ["/export/"]
EXPOSE :80
EXPOSE :21
EXPOSE :8800
CMD ["/usr/bin/startup"]

