# see https://github.com/fubar2/toolfactory
#
# copyright ross lazarus (ross stop lazarus at gmail stop com) May 2012
#
# all rights reserved
# Licensed under the LGPL
# suggestions for improvement and bug fixes welcome at
# https://github.com/fubar2/toolfactory
#
# July 2020: BCC was fun and I feel like rip van winkle after 5 years.
# Decided to
# 1. Fix the toolfactory so it works - done for simplest case
# 2. Fix planemo so the toolfactory function works
# 3. Rewrite bits using galaxyxml functions where that makes sense - done

import argparse
import copy
import os
import subprocess
import shutil
import sys
import tarfile
import tempfile
import time

myversion = "V2.2 April 2021"
verbose = True
debug = True
toolFactoryURL = "https://github.com/fubar2/toolfactory"

def timenow():
    """return current time as a string"""
    return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(time.time()))

class ToolTester():
    # requires highly insecure docker settings - like write to tool_conf.xml and to tools !
    # if in a container possibly not so courageous.
    # Fine on your own laptop but security red flag for most production instances
    # uncompress passed tar, run planemo and rebuild a new tarball with tests

    def __init__(self, args=None, in_tool_archive='/galaxy-central/tools/newtool/newtool_toolshed.gz', new_tool_archive=None):
        self.args = args
        self.new_tool_archive = new_tool_archive
        assert tarfile.is_tarfile(in_tool_archive)
        # this is not going to go well with arbitrary names. TODO introspect tool xml!
        self.tooloutdir = "./tfout"
        self.repdir = "./TF_run_report"
        self.testdir = os.path.join(self.tooloutdir, "test-data")
        if not os.path.exists(self.tooloutdir):
            os.mkdir(self.tooloutdir)
        if not os.path.exists(self.testdir):
            os.mkdir(self.testdir)
        if not os.path.exists(self.repdir):
            os.mkdir(self.repdir)
        tff = tarfile.open(in_tool_archive, "r:*")
        flist = tff.getnames()
        ourdir = os.path.commonpath(flist) # eg pyrevpos
        self.tool_name = ourdir
        ourxmls = [x for x in flist if x.lower().endswith('.xml') and os.path.split(x)[0] == ourdir]
        assert len(ourxmls) > 0
        self.ourxmls = ourxmls # [os.path.join(tool_path,x) for x in ourxmls]
        res = tff.extractall()
        tff.close()
        self.update_tests(ourdir)
        self.makeTool()
        self.moveRunOutputs()
        self.makeToolTar()

    def call_planemo(self,xmlpath,ourdir):
        penv = os.environ
        penv['HOME'] = '/home/ross/galaxy-release_21.01'
        toolfile = os.path.split(xmlpath)[1]
        tool_name = self.tool_name
        tool_test_output = f"{tool_name}_planemo_test_report.html"
        cll = [
            "planemo",
            "test",
            "--test_output",
            os.path.abspath(tool_test_output),
            "--galaxy_root",
            self.args.galaxy_root,
            "--update_test_data",
            os.path.abspath(xmlpath),
        ]
        print(cll)
        p = subprocess.run(
            cll,
            capture_output=True,
            encoding='utf8',
            env = penv,
            shell=False,
        )
        return p

    def makeTool(self):
        """write xmls and input samples into place"""
        for xreal in self.ourxmls:
            x = os.path.split(xreal)[1]
            xout = os.path.join(self.tooloutdir,x)
            shutil.copyfile(xreal, xout)
        # for p in self.infiles:
            # pth = p["name"]
            # dest = os.path.join(self.testdir, "%s_sample" % p["infilename"])
            # shutil.copyfile(pth, dest)
            # dest = os.path.join(self.repdir, "%s_sample" % p["infilename"])
            # shutil.copyfile(pth, dest)

    def makeToolTar(self):
        """move outputs into test-data and prepare the tarball"""
        excludeme = "_planemo_test_report.html"

        def exclude_function(tarinfo):
            filename = tarinfo.name
            return None if filename.endswith(excludeme) else tarinfo

        newtar = 'new_%s_toolshed.gz' % self.tool_name
        ttf = tarfile.open(newtar, "w:gz")
        ttf.add(name=self.tooloutdir,
            arcname=self.tool_name,
            filter=exclude_function)
        ttf.close()
        shutil.copyfile(newtar, self.new_tool_archive)

    def moveRunOutputs(self):
        """need to move planemo or run outputs into toolfactory collection"""
        with os.scandir(self.tooloutdir) as outs:
            for entry in outs:
                if not entry.is_file():
                    continue
                if "." in entry.name:
                    _, ext = os.path.splitext(entry.name)
                    if ext in [".tgz", ".json"]:
                        continue
                    if ext in [".yml", ".xml", ".yaml"]:
                        newname = f"{entry.name.replace('.','_')}.txt"
                    else:
                        newname = entry.name
                else:
                    newname = f"{entry.name}.txt"
                dest = os.path.join(self.repdir, newname)
                src = os.path.join(self.tooloutdir, entry.name)
                shutil.copyfile(src, dest)
        with os.scandir('.') as outs:
            for entry in outs:
                if not entry.is_file():
                    continue
                if "." in entry.name:
                    _, ext = os.path.splitext(entry.name)
                    if ext in [".yml", ".xml", ".yaml"]:
                        newname = f"{entry.name.replace('.','_')}.txt"
                    else:
                        newname = entry.name
                else:
                    newname = f"{entry.name}.txt"
                dest = os.path.join(self.repdir, newname)
                src =entry.name
                shutil.copyfile(src, dest)
        if True or self.args.include_tests:
            with os.scandir(self.testdir) as outs:
                for entry in outs:
                    if (not entry.is_file()) or entry.name.endswith(
                        "_planemo_test_report.html"
                    ):
                        continue
                    if "." in entry.name:
                        _, ext = os.path.splitext(entry.name)
                        if ext in [".tgz", ".json"]:
                            continue
                        if ext in [".yml", ".xml", ".yaml"]:
                            newname = f"{entry.name.replace('.','_')}.txt"
                        else:
                            newname = entry.name
                    else:
                        newname = f"{entry.name}.txt"
                    dest = os.path.join(self.repdir, newname)
                    src = os.path.join(self.testdir, entry.name)
                    shutil.copyfile(src, dest)


    def update_tests(self,ourdir):
        for xmlf in self.ourxmls:
            capture = self.call_planemo(xmlf,ourdir)
            #sys.stderr.write('%s, stdout=%s, stderr=%s' % (xmlf, capture.stdout, capture.stdout))
            print('%s, stdout=%s, stderr=%s' % (capture.stdout, capture.stdout,xmlf))

def main():
    """
    This is a Galaxy wrapper.
    It expects to be called by a special purpose tool.xml

    """
    parser = argparse.ArgumentParser()
    a = parser.add_argument
    a("--in_tool_archive", default=None)
    a("--new_tested_tool_archive", default=None)
    a("--galaxy_root", default="/home/ross/galaxy-release_21.01/")
    args = parser.parse_args()
    print('Hello from',os.getcwd())
    tt = ToolTester(args=args, in_tool_archive=args.in_tool_archive, new_tool_archive=args.new_tested_tool_archive)

if __name__ == "__main__":
    main()
