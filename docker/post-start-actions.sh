
# python workflow_import.py <api_key> <galaxy_url> '/path/to/workflow/file [--add_to_menu]'
python $GALAXY_ROOT/scripts/api/workflow_import.py \
  $GALAXY_DEFAULT_ADMIN_KEY \
  http://127.0.0.1:$PORT \
  file://localhost/$GALAXY_ROOT/workflows/TF_example_wf.ga --add_to_menu

