 # Galaxy - Toolshed Docker image
# Derived from bgruening stable galaxy 
# VERSION       0.2
# patches startup so the below will install a workflow dropped into $GALAXY_ROOT/workflows
# use docker run -p 8080:80  -d -e GALAXY_AUTO_UPDATE_WORKFLOWS=/galaxy-central/workflows/TF_sample_wf.ga -v /home/ubuntu/galaxy_storage/:/export/  toolfactory
#FROM quay.io/bgruening/galaxy:20.05 as gdbase
FROM quay.io/bgruening/galaxy:20.05 as galaxy-dev
MAINTAINER Ross Lazarus ross.lazarus@gmail.com

RUN apt-get update -y && apt-get install -y git python3-dev gcc sqlite3\
 && git clone https://github.com/fubar2/galaxy.git /tmp/galxxxx \
 && cp -r /tmp/galxxxx/* /galaxy-central/ \
 && . /galaxy_venv/bin/activate && /galaxy_venv/bin/python3 -m pip install --upgrade pip \
 && /galaxy_venv/bin/python3 -m pip install -r $GALAXY_ROOT/requirements.txt
# cleanup dance
RUN find $GALAXY_ROOT/ -name '*.pyc' -delete | true \
    && find /usr/lib/ -name '*.pyc' -delete | true \
    && find /var/log/ -name '*.log' -delete | true \
    && find $GALAXY_VIRTUAL_ENV -name '*.pyc' -delete | true \
    && rm -rf /tmp/* /root/.cache/ /var/cache/* $GALAXY_ROOT/client/node_modules/ $GALAXY_VIRTUAL_ENV/src/ /home/galaxy/.cache/ /home/galaxy/.npm


ENV GALAXY_CONFIG_BRAND=ToolFactory
ENV GALAXY_LOGGING="full"
# ENV GALAXY_AUTO_UPDATE_TOOLS=/tftools/toolfactory_tools.yaml
# ensure triggering post-start-actions.sh

# RUN add-tool-shed --url 'http://testtoolshed.g2.bx.psu.edu/' --name 'Test Tool Shed'


FROM galaxy-dev

COPY tftools/ /tftools/
# things needed for post-install 
RUN mkdir -p /export
ADD tftools/tfwelcome.html /export/welcome.html
ADD tftools/tfwelcome.html $GALAXY_ROOT/lib/galaxy/web/framework/static/welcome.html
RUN chown $GALAXY_USER:$GALAXY_USER $GALAXY_ROOT/lib/galaxy/web/framework/static/welcome.html
# ADD my_tool_list.yml /tftools/toolfactory_tools.yaml
# ADD tftools/tf_tool_conf.xml $GALAXY_ROOT/config/tf_tool_conf.xml
# RUN chown $GALAXY_USER:$GALAXY_USER $GALAXY_ROOT/config/tf_tool_conf.xml

# NOTE above does work but takes 1-2 minutes
# ENV GALAXY_CONFIG_TOOL_CONFIG_FILE=config/tool_conf.xml.sample,config/tf_tool_conf.xml,config/shed_tool_conf.xml.sample

ADD tftools/datatypes_conf.xml $GALAXY_ROOT/lib/galaxy/config/sample/datatypes_conf.xml.sample
RUN chown $GALAXY_USER:$GALAXY_USER $GALAXY_ROOT/lib/galaxy/config/sample/datatypes_conf.xml.sample
ADD tftools/post-start-actions.sh $GALAXY_ROOT/config/post-start-actions.sh
ADD tftools/TFstartup.sh /usr/bin/tfstart
ADD tftools/post-start-actions.sh /export/post-start-actions.sh
RUN chmod a+xr /export/post-start-actions.sh \
 && chmod a+xr /tftools/postinstall.py \
 && chmod a+xr $GALAXY_ROOT/config/post-start-actions.sh \ 
 && chmod a+xr /usr/bin/tfstart
ADD tftools/tool_shed.yml $GALAXY_ROOT/config/tool_shed.yml
COPY tftools/tool_shed.yml $GALAXY_ROOT/lib/galaxy/config/sample/tool.shed.yml.sample
COPY tftools/requirements.txt $GALAXY_ROOT
# Add Galaxy interactive tours
# ADD ./rna-workbench-tours/* $GALAXY_ROOT/config/plugins/tours/
# Add data library definition file
# ADD library_data.yaml $GALAXY_ROOT/library_data.yaml
ENV $GALAXY_DEFAULT_ADMIN_USER="admin"
# ENV GALAXY_CONFIG_TOOL_CONFIG_FILE=$GALAXY_ROOT/config/tf_tool_conf.xml,config/tool_conf.xml.sample
# works but does not install dependencies - done in postinstall

RUN mkdir -p /galaxy-central/static/scripts && cd /galaxy/central/static/scripts \
  && ln -s galaxy-central/static/dist bundled

RUN chown -R $GALAXY_USER:$GALAXY_USER /tftools 


VOLUME ["/export/", "/data/", "/var/lib/docker"]
EXPOSE :80
EXPOSE :21
EXPOSE :8800
EXPOSE :9009
CMD ["/usr/bin/tfstart"]

