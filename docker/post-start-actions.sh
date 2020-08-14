# hook to install tf demo workflow
workflow-install -w $GALAXY_HOME/workflows -g http://localhost:$PORT \
        -u $GALAXY_DEFAULT_ADMIN_USER -p $GALAXY_DEFAULT_ADMIN_PASSWORD --add_to_menu
