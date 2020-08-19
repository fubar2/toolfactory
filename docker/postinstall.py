# need this until I find the right way to do these things..

from bioblend import galaxy

wfpath = "/tftools/TF_example_wf.ga"
hispath = "/tftools/tfsamplehistory.tar.gz"
gi = galaxy.GalaxyInstance(url='http://127.0.0.1', key='fakekey')
#h = gi.histories.get_most_recently_used_history()
x = gi.histories.import_history(file_path=hispath, url=None)
x = gi.workflows.import_workflow_from_local_path(wfpath, publish=True)

