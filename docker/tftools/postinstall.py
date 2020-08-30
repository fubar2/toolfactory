from sqlite3 import Error


def hacktsuser():
    dbfile = "/galaxy-central/database/community.sqlite"
    conn = None
    try:
        conn = sqlite3.connect(dbfile)
    except Error as e:
        print(e)

    now = datetime.datetime.now()
    auser = (now, now, "admin@galaxy.org", "fubar", "password", "", "", "", "")
    sql = "UPDATE galaxy_user SET username = 'fubar', password = 'password' WHERE email = 'admin@galaxy.org'"
    #  (create_time,update_time,email,username,password,external,deleted,purged) VALUES(?,?,?,?,?,?,?,?)
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    print("### executed %s" % sql)
    sql = "UPDATE api_keys SET key='fakekey' where id = 1"
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    print("### executed %s" % sql)
    conn.close()

def eph_galaxy_load(toolname='tool_factory_2',owner="fubar"):
    """load the new tool from the toolshed the old skool dependency way
    bioconda is too stale to use for this
    """
    cll = [
        "shed-tools",
        "install",
        "-g",
        "http://localhost",
        "--latest",
        "-a",
        "fakekey",
        "--name",
        toolname,
        "--owner",
        owner,
        "--toolshed",
        "https://toolshed.g2.bx.psu.edu",
        "--section_label",
        "Tool Makers",
        "--install_tool_dependencies",
        "--skip_install_resolver_dependencies",
        "--skip_install_repository_dependencies",
    ]
    print("running\n", " ".join(cll))
    p = subprocess.run(cll, shell=False, )
    if p.returncode != 0:
        print(
            "Repository %s installation returned %d"
            % (self.args.tool_name, p.returncode)
        )
    else:
        print("installed %s" % self.args.tool_name)
    tout.close()
    return p.returncode


installme = ["rgTF2"]

#eph_galaxy_load()
wfpath = "/tftools/TF_example_wf.ga"
hispath = "/tftools/tfsamplehistory.tar.gz"
gi = galaxy.GalaxyInstance(url="http://127.0.0.1", key="fakekey")
# h = gi.histories.get_most_recently_used_history()
x = gi.histories.import_history(file_path=hispath, url=None)
print("Import history = %s" % str(x))
x = gi.workflows.import_workflow_from_local_path(wfpath, publish=True)
print("Import workflow = %s" % str(x))
# tools = gi.tools.get_tools(tool_id=None, name=None, trackster=None)
# for tool in tools:
    # tid = tool["id"]
    # if tid in installme:
        # gi.tools.install_dependencies(tid)
        # print("### Installed dependencies for tool_id %s" % tid)
hacktsuser()
