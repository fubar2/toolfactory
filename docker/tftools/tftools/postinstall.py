# need this until I find the right way to do these things..

from bioblend import galaxy

wfpath = "/tftools/TF_example_wf.ga"
hispath = "/tftools/tfsamplehistory.tar.gz"
gi = galaxy.GalaxyInstance(url="http://127.0.0.1", key="fakekey")
# h = gi.histories.get_most_recently_used_history()
x = gi.histories.import_history(file_path=hispath, url=None)
print("Import history = %s" % str(x))
x = gi.workflows.import_workflow_from_local_path(wfpath, publish=True)
print("Import workflow = %s" % str(x))
tools = gi.tools.get_tools(tool_id=None, name=None, trackster=None)
for t in tools:
    tid = t["id"]
    if tid in ["rgTF2", "planemotest"]:
        gi.tools.install_dependencies(tid)
        print("Installed dependencies for tool_id %s" % tid)
