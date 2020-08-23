import argparse
import tarfile
import os
import shutil
import subprocess

from bioblend import galaxy

REPDIR = "TF_run_report_tempdir"
TAROUTDIR = "taroutdir"


def planemo_shedload(args):
    """
    planemo shed_create --shed_target testtoolshed
    planemo shed_update --check_diff --shed_target testtoolshed
    """
    cll = ['planemo', 'shed_create', '--shed_target','local'] 
    p = subprocess.run(cll, shell=False,cwd=TAROUTDIR )
    if p.returncode != 0:
        print('Repository %s exists' % args.tool_name)
    else:
        print('initiated %s' % args.tool_name)
    cll = ['planemo', 'shed_upload', '--shed_target','local','-r','--owner','fubar',
        '--name',args.tool_name,'--shed_key',args.toolshed_api_key,'--tar',os.path.join('../',args.tool_tgz)] 
    p = subprocess.run(cll, shell=False,cwd=TAROUTDIR)
    print('Ran',' '.join(cll),'got',p.returncode)
    return p.returncode

    
def planemo_test(args):
    """planemo is a requirement so is available
    """
    cll = ['planemo', 'test', '--galaxy_root', args.galaxy_root, 
        args.tool_name]
    p = subprocess.run(cll, shell=False)
    ols = os.listdir('.')
    for fn in ols:
        if '.' in fn:
            ofne = os.path.splitext(fn)[1]
        else:
            ofne = '.txt'
        ofn = '%s%s' % (fn.replace('.','_'),ofne)
        shutil.copyfile(fn,os.path.join(REPDIR,ofn))
        
    return p.returncode


def eph_galaxy_load(args):
    """
    shed-tools install [-h] [-v] [--log_file LOG_FILE] [-g GALAXY] [-u USER]
                   [-p PASSWORD] [-a API_KEY] [-t TOOL_LIST_FILE]
                   [-y TOOL_YAML] [--name NAME] [--owner OWNER]
                   [--revisions [REVISIONS [REVISIONS ...]]]
                   [--toolshed TOOL_SHED_URL] [--install_tool_dependencies]
                   [--skip_install_resolver_dependencies]
                   [--skip_install_repository_dependencies] [--test]
                   [--test_existing] [--test_json TEST_JSON]
                   [--test_user_api_key TEST_USER] [--test_user TEST_USER]
                   [--parallel_tests PARALLEL_TESTS]
                   [--section TOOL_PANEL_SECTION_ID]
                   [--section_label TOOL_PANEL_SECTION_LABEL] [--latest]
    """
    cll = ['shed-tools', 'install', '-g', args.galaxy_url, '--latest', 
       '-a', args.galaxy_api_key , '--name', args.tool_name, '--owner','fubar',
       '--toolshed', args.toolshed_url,
       '--section_label','Generated Tools','--install_tool_dependencies',] 
    print('running\n',' '.join(cll))
    p = subprocess.run(cll, shell=False)
    if p.returncode != 0:
        print('Repository %s installation returned %d' % (args.tool_name,p.retcode))
    else:
        print('installed %s' % args.tool_name)
    return p.returncode

parser = argparse.ArgumentParser()
a = parser.add_argument
a("--tool_name",default="")
a("--tool_tgz", default="")
a("--install_here", default="yes")
a("--toolshed_api_key",default="d46e5ed0e242ed52c6e1f506b5d7f9f7")
a("--toolshed_url",default="http://localhost:9009")
a("--galaxy_api_key",default="fbdd3c2eecd191e88939fffc02eeeaf8")
a("--galaxy_url",default="http://localhost:8080")
a("--tool_section",default="Generated Tools")
a("--galaxy_root", default="/galaxy-central")
args = parser.parse_args()
tf = tarfile.open(args.tool_tgz, "r:gz")
if os.path.isdir(TAROUTDIR):
    shutil.rmtree(TAROUTDIR, ignore_errors=True, onerror=None)
os.mkdir(TAROUTDIR)
tf.extractall(path=TAROUTDIR)
tf.close()
planemodir = TAROUTDIR
if True or planemo_test(args):
    if args.install_here == "yes":
        planemo_shedload(args)
        eph_galaxy_load(args)
    
else:
    stderr.write('Planemo test failed - tool %s was not installed' % args.tool_name)

