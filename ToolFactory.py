
# see https://github.com/fubar2/toolfactory
#
# copyright ross lazarus (ross stop lazarus at gmail stop com) May 2012
#
# all rights reserved
# Licensed under the LGPL
# suggestions for improvement and bug fixes welcome at
# https://github.com/fubar2/toolfactory
#
# April 2021: Refactored into two tools - generate and test/install
# as part of GTN tutorial development and biocontainer adoption
# The tester runs planemo on a non-tested archive, creates the test outputs
# and returns a new proper tool with test.
# The tester was generated from the ToolFactory_tester.py script


import argparse
import copy
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

from bioblend import ConnectionError
from bioblend import galaxy
from bioblend import toolshed

import galaxyxml.tool as gxt
import galaxyxml.tool.parameters as gxtp

import lxml.etree as ET

import yaml

myversion = "V2.3 April 2021"
verbose = True
debug = True
toolFactoryURL = "https://github.com/fubar2/toolfactory"
FAKEEXE = "~~~REMOVE~~~ME~~~"
# need this until a PR/version bump to fix galaxyxml prepending the exe even
# with override.


def timenow():
    """return current time as a string"""
    return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(time.time()))

cheetah_escape_table = {"$": "\\$", "#": "\\#"}

def cheetah_escape(text):
    """Produce entities within text."""
    return "".join([cheetah_escape_table.get(c, c) for c in text])

def parse_citations(citations_text):
    """"""
    citations = [c for c in citations_text.split("**ENTRY**") if c.strip()]
    citation_tuples = []
    for citation in citations:
        if citation.startswith("doi"):
            citation_tuples.append(("doi", citation[len("doi") :].strip()))
        else:
            citation_tuples.append(("bibtex", citation[len("bibtex") :].strip()))
    return citation_tuples

class ToolTester():
    # requires highly insecure docker settings - like write to tool_conf.xml and to tools !
    # if in a container possibly not so courageous.
    # Fine on your own laptop but security red flag for most production instances
    # uncompress passed tar, run planemo and rebuild a new tarball with tests

    def __init__(self, report_dir, in_tool_archive, new_tool_archive, include_tests, galaxy_root):
        self.new_tool_archive = new_tool_archive
        self.include_tests = include_tests
        self.galaxy_root = galaxy_root
        self.repdir = report_dir
        assert in_tool_archive and tarfile.is_tarfile(in_tool_archive)
        # this is not going to go well with arbitrary names. TODO introspect tool xml!
        tff = tarfile.open(in_tool_archive, "r:*")
        flist = tff.getnames()
        ourdir = os.path.commonpath(flist) # eg pyrevpos
        self.tool_name = ourdir
        ourxmls = [x for x in flist if x.lower().endswith('.xml') and os.path.split(x)[0] == ourdir]
        # planemo_test/planemo_test.xml
        assert len(ourxmls) > 0
        self.ourxmls = ourxmls # [os.path.join(tool_path,x) for x in ourxmls]
        res = tff.extractall()
        tff.close()
        self.update_tests(ourdir)
        self.tooloutdir = ourdir
        self.testdir = os.path.join(self.tooloutdir, "test-data")
        if not os.path.exists(self.tooloutdir):
            os.mkdir(self.tooloutdir)
        if not os.path.exists(self.testdir):
            os.mkdir(self.testdir)
        if not os.path.exists(self.repdir):
            os.mkdir(self.repdir)
        if not os.path.exists(self.tooloutdir):
            os.mkdir(self.tooloutdir)
        if not os.path.exists(self.testdir):
            os.mkdir(self.testdir)
        if not os.path.exists(self.repdir):
            os.mkdir(self.repdir)
        self.moveRunOutputs()
        self.makeToolTar()

    def call_planemo(self,xmlpath,ourdir):
        penv = os.environ
        penv['HOME'] = os.path.join(self.galaxy_root,'planemo')
        #penv["GALAXY_VIRTUAL_ENV"] = os.path.join(penv['HOME'],'.planemo','gx_venv_3.9')
        penv["PIP_CACHE_DIR"] = os.path.join(self.galaxy_root,'pipcache')
        toolfile = os.path.split(xmlpath)[1]
        tool_name = self.tool_name
        tool_test_output = os.path.join(self.repdir, f"{tool_name}_planemo_test_report.html")
        cll = ["planemo",
            "test",
            #"--job_config_file",
            # os.path.join(self.galaxy_root,"config","job_conf.xml"),
            #"--galaxy_python_version",
            #"3.9",
            "--test_output",
            os.path.abspath(tool_test_output),
            "--galaxy_root",
            self.galaxy_root,
            "--update_test_data",
            os.path.abspath(xmlpath),
        ]
        print("Call planemo cl =", cll)
        p = subprocess.run(
            cll,
            capture_output=True,
            encoding='utf8',
            env = penv,
            shell=False,
        )
        return p

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

    def move_One(self,scandir):
        with os.scandir('.') as outs:
            for entry in outs:
                newname = entry.name
                if not entry.is_file() or entry.name.endswith('_sample'):
                    continue
                if not (entry.name.endswith('.html') or entry.name.endswith('.gz') or entry.name.endswith(".tgz")):
                    fname, ext = os.path.splitext(entry.name)
                    if len(ext) > 1:
                        newname = f"{fname}_{ext[1:]}.txt"
                    else:
                        newname = f"{fname}.txt"
                dest = os.path.join(self.repdir, newname)
                src = entry.name
                shutil.copyfile(src, dest)

    def moveRunOutputs(self):
        """need to move planemo or run outputs into toolfactory collection"""
        self.move_One(self.tooloutdir)
        self.move_One('.')
        if self.include_tests:
            self.move_One(self.testdir)

    def update_tests(self,ourdir):
        for xmlf in self.ourxmls:
            capture = self.call_planemo(xmlf,ourdir)
            logf = open(f"%s_run_report" % (self.tool_name),'w')
            logf.write("stdout:")
            logf.write(capture.stdout)
            logf.write("stderr:")
            logf.write(capture.stderr)


class ToolConfUpdater():
    # update config/tool_conf.xml with a new tool unpacked in /tools
    # requires highly insecure docker settings - like write to tool_conf.xml and to tools !
    # if in a container possibly not so courageous.
    # Fine on your own laptop but security red flag for most production instances

    def __init__(self, args, tool_conf_path, new_tool_archive_path, new_tool_name, tool_dir):
        self.args = args
        self.tool_conf_path = tool_conf_path
        self.our_name = 'ToolFactory'
        tff = tarfile.open(new_tool_archive_path, "r:*")
        flist = tff.getnames()
        ourdir = os.path.commonpath(flist) # eg pyrevpos
        self.tool_id = ourdir # they are the same for TF tools
        ourxml = [x for x in flist if x.lower().endswith('.xml')]
        res = tff.extractall(tool_dir)
        tff.close()
        self.update_toolconf(ourdir,ourxml)

    def install_deps(self):
        gi = galaxy.GalaxyInstance(url=self.args.galaxy_url, key=self.args.galaxy_api_key)
        x = gi.tools.install_dependencies(self.tool_id)
        print(f"Called install_dependencies on {self.tool_id} - got {x}")

    def update_toolconf(self,ourdir,ourxml): # path is relative to tools
        updated = False
        tree = ET.parse(self.tool_conf_path)
        root = tree.getroot()
        hasTF = False
        TFsection = None
        for e in root.findall('section'):
            if e.attrib['name'] == self.our_name:
                hasTF = True
                TFsection = e
        if not hasTF:
            TFsection = ET.Element('section')
            root.insert(0,TFsection) # at the top!
        our_tools = TFsection.findall('tool')
        conf_tools = [x.attrib['file'] for x in our_tools]
        for xml in ourxml:   # may be > 1
            if not xml in conf_tools: # new
                updated = True
                ET.SubElement(TFsection, 'tool', {'file':xml})
        ET.indent(tree)
        tree.write(self.tool_conf_path, pretty_print=True)
        if False and self.args.packages and self.args.packages > '':
            self.install_deps()

class ScriptRunner:
    """Wrapper for an arbitrary script
    uses galaxyxml

    """

    def __init__(self, args=None):  # noqa
        """
        prepare command line cl for running the tool here
        and prepare elements needed for galaxyxml tool generation
        """
        self.ourcwd = os.getcwd()
        self.collections = []
        if len(args.collection) > 0:
            try:
                self.collections = [
                    json.loads(x) for x in args.collection if len(x.strip()) > 1
                ]
            except Exception:
                print(
                    f"--collections parameter {str(args.collection)} is malformed - should be a dictionary"
                )
        try:
            self.infiles = [
                json.loads(x) for x in args.input_files if len(x.strip()) > 1
            ]
        except Exception:
            print(
                f"--input_files parameter {str(args.input_files)} is malformed - should be a dictionary"
            )
        try:
            self.outfiles = [
                json.loads(x) for x in args.output_files if len(x.strip()) > 1
            ]
        except Exception:
            print(
                f"--output_files parameter {args.output_files} is malformed - should be a dictionary"
            )
        try:
            self.addpar = [
                json.loads(x) for x in args.additional_parameters if len(x.strip()) > 1
            ]
        except Exception:
            print(
                f"--additional_parameters {args.additional_parameters} is malformed - should be a dictionary"
            )
        try:
            self.selpar = [
                json.loads(x) for x in args.selecttext_parameters if len(x.strip()) > 1
            ]
        except Exception:
            print(
                f"--selecttext_parameters {args.selecttext_parameters} is malformed - should be a dictionary"
            )
        self.args = args
        self.cleanuppar()
        self.lastclredirect = None
        self.lastxclredirect = None
        self.cl = []
        self.xmlcl = []
        self.is_positional = self.args.parampass == "positional"
        if self.args.sysexe:
            if ' ' in self.args.sysexe:
                self.executeme = self.args.sysexe.split(' ')
            else:
                self.executeme = [self.args.sysexe, ]
        else:
            if self.args.packages:
                self.executeme = [self.args.packages.split(",")[0].split(":")[0].strip(), ]
            else:
                self.executeme = None
        aCL = self.cl.append
        aXCL = self.xmlcl.append
        assert args.parampass in [
            "0",
            "argparse",
            "positional",
        ], 'args.parampass must be "0","positional" or "argparse"'
        self.tool_name = re.sub("[^a-zA-Z0-9_]+", "", args.tool_name)
        self.tool_id = self.tool_name
        self.newtool = gxt.Tool(
            self.tool_name,
            self.tool_id,
            self.args.tool_version,
            self.args.tool_desc,
            FAKEEXE,
        )
        self.newtarpath = "%s_toolshed.gz" % self.tool_name
        self.tooloutdir = "./tfout"
        self.repdir = "./TF_run_report"
        self.testdir = os.path.join(self.tooloutdir, "test-data")
        if not os.path.exists(self.tooloutdir):
            os.mkdir(self.tooloutdir)
        if not os.path.exists(self.testdir):
            os.mkdir(self.testdir)
        if not os.path.exists(self.repdir):
            os.mkdir(self.repdir)
        self.tinputs = gxtp.Inputs()
        self.toutputs = gxtp.Outputs()
        self.testparam = []
        if self.args.script_path:
            self.prepScript()
        if self.args.command_override:
            scos = open(self.args.command_override, "r").readlines()
            self.command_override = [x.rstrip() for x in scos]
        else:
            self.command_override = None
        if self.args.test_override:
            stos = open(self.args.test_override, "r").readlines()
            self.test_override = [x.rstrip() for x in stos]
        else:
            self.test_override = None
        if self.args.script_path:
            for ex in self.executeme:
                aCL(ex)
                aXCL(ex)
            aCL(self.sfile)
            aXCL("$runme")
        else:
            for ex in self.executeme:
                aCL(ex)
                aXCL(ex)

        if self.args.parampass == "0":
            self.clsimple()
        else:
            if self.args.parampass == "positional":
                self.prepclpos()
                self.clpositional()
            else:
                self.prepargp()
                self.clargparse()

    def clsimple(self):
        """no parameters or repeats - uses < and > for i/o"""
        aCL = self.cl.append
        aXCL = self.xmlcl.append
        if len(self.infiles) > 0:
            aCL("<")
            aCL(self.infiles[0]["infilename"])
            aXCL("<")
            aXCL("$%s" % self.infiles[0]["infilename"])
        if len(self.outfiles) > 0:
            aCL(">")
            aCL(self.outfiles[0]["name"])
            aXCL(">")
            aXCL("$%s" % self.outfiles[0]["name"])
        if self.args.cl_user_suffix:  # DIY CL end
            clp = shlex.split(self.args.cl_user_suffix)
            for c in clp:
                aCL(c)
                aXCL(c)

    def prepargp(self):
        clsuffix = []
        xclsuffix = []
        for i, p in enumerate(self.infiles):
            nam = p["infilename"]
            if p["origCL"].strip().upper() == "STDIN":
                appendme = [
                    nam,
                    nam,
                    "< %s" % nam,
                ]
                xappendme = [
                    nam,
                    nam,
                    "< $%s" % nam,
                ]
            else:
                rep = p["repeat"] == "1"
                over = ""
                if rep:
                    over = f'#for $rep in $R_{nam}:\n--{nam} "$rep.{nam}"\n#end for'
                appendme = [p["CL"], p["CL"], ""]
                xappendme = [p["CL"], "$%s" % p["CL"], over]
            clsuffix.append(appendme)
            xclsuffix.append(xappendme)
        for i, p in enumerate(self.outfiles):
            if p["origCL"].strip().upper() == "STDOUT":
                self.lastclredirect = [">", p["name"]]
                self.lastxclredirect = [">", "$%s" % p["name"]]
            else:
                clsuffix.append([p["name"], p["name"], ""])
                xclsuffix.append([p["name"], "$%s" % p["name"], ""])
        for p in self.addpar:
            nam = p["name"]
            rep = p["repeat"] == "1"
            if rep:
                over = f'#for $rep in $R_{nam}:\n--{nam} "$rep.{nam}"\n#end for'
            else:
                over = p["override"]
            clsuffix.append([p["CL"], nam, over])
            xclsuffix.append([p["CL"], '"$%s"' % nam, over])
        for p in self.selpar:
            clsuffix.append([p["CL"], p["name"], p["override"]])
            xclsuffix.append([p["CL"], '"$%s"' % p["name"], p["override"]])
        self.xclsuffix = xclsuffix
        self.clsuffix = clsuffix

    def prepclpos(self):
        clsuffix = []
        xclsuffix = []
        for i, p in enumerate(self.infiles):
            if p["origCL"].strip().upper() == "STDIN":
                appendme = [
                    "999",
                    p["infilename"],
                    "< $%s" % p["infilename"],
                ]
                xappendme = [
                    "999",
                    p["infilename"],
                    "< $%s" % p["infilename"],
                ]
            else:
                appendme = [p["CL"], p["infilename"], ""]
                xappendme = [p["CL"], "$%s" % p["infilename"], ""]
            clsuffix.append(appendme)
            xclsuffix.append(xappendme)
        for i, p in enumerate(self.outfiles):
            if p["origCL"].strip().upper() == "STDOUT":
                self.lastclredirect = [">", p["name"]]
                self.lastxclredirect = [">", "$%s" % p["name"]]
            else:
                clsuffix.append([p["CL"], p["name"], ""])
                xclsuffix.append([p["CL"], "$%s" % p["name"], ""])
        for p in self.addpar:
            nam = p["name"]
            rep = p["repeat"] == "1"  # repeats make NO sense
            if rep:
                print(f'### warning. Repeats for {nam} ignored - not permitted in positional parameter command lines!')
            over = p["override"]
            clsuffix.append([p["CL"], nam, over])
            xclsuffix.append([p["CL"], '"$%s"' % nam, over])
        for p in self.selpar:
            clsuffix.append([p["CL"], p["name"], p["override"]])
            xclsuffix.append([p["CL"], '"$%s"' % p["name"], p["override"]])
        clsuffix.sort()
        xclsuffix.sort()
        self.xclsuffix = xclsuffix
        self.clsuffix = clsuffix

    def prepScript(self):
        rx = open(self.args.script_path, "r").readlines()
        rx = [x.rstrip() for x in rx]
        rxcheck = [x.strip() for x in rx if x.strip() > ""]
        assert len(rxcheck) > 0, "Supplied script is empty. Cannot run"
        self.script = "\n".join(rx)
        fhandle, self.sfile = tempfile.mkstemp(
            prefix=self.tool_name, suffix="_%s" % (self.executeme[0])
        )
        tscript = open(self.sfile, "w")
        tscript.write(self.script)
        tscript.close()
        self.spacedScript = [f"    {x}" for x in rx if x.strip() > ""]
        rx.insert(0,'#raw')
        rx.append('#end raw')
        self.escapedScript = rx
        art = "%s.%s" % (self.tool_name, self.executeme[0])
        artifact = open(art, "wb")
        artifact.write(bytes(self.script, "utf8"))
        artifact.close()

    def cleanuppar(self):
        """ positional parameters are complicated by their numeric ordinal"""
        if self.args.parampass == "positional":
            for i, p in enumerate(self.infiles):
                assert (
                    p["CL"].isdigit() or p["CL"].strip().upper() == "STDIN"
                ), "Positional parameters must be ordinal integers - got %s for %s" % (
                    p["CL"],
                    p["label"],
                )
            for i, p in enumerate(self.outfiles):
                assert (
                    p["CL"].isdigit() or p["CL"].strip().upper() == "STDOUT"
                ), "Positional parameters must be ordinal integers - got %s for %s" % (
                    p["CL"],
                    p["name"],
                )
            for i, p in enumerate(self.addpar):
                assert p[
                    "CL"
                ].isdigit(), "Positional parameters must be ordinal integers - got %s for %s" % (
                    p["CL"],
                    p["name"],
                )
        for i, p in enumerate(self.infiles):
            infp = copy.copy(p)
            infp["origCL"] = infp["CL"]
            if self.args.parampass in ["positional", "0"]:
                infp["infilename"] = infp["label"].replace(" ", "_")
            else:
                infp["infilename"] = infp["CL"]
            self.infiles[i] = infp
        for i, p in enumerate(self.outfiles):
            p["origCL"] = p["CL"]  # keep copy
            self.outfiles[i] = p
        for i, p in enumerate(self.addpar):
            p["origCL"] = p["CL"]
            self.addpar[i] = p

    def clpositional(self):
        # inputs in order then params
        aCL = self.cl.append
        for (k, v, koverride) in self.clsuffix:
            if " " in v:
                aCL("%s" % v)
            else:
                aCL(v)
        aXCL = self.xmlcl.append
        for (k, v, koverride) in self.xclsuffix:
            aXCL(v)
        if self.lastxclredirect:
            aXCL(self.lastxclredirect[0])
            aXCL(self.lastxclredirect[1])
        if self.args.cl_user_suffix:  # DIY CL end
            clp = shlex.split(self.args.cl_user_suffix)
            for c in clp:
                aCL(c)
                aXCL(c)


    def clargparse(self):
        """argparse style"""
        aCL = self.cl.append
        aXCL = self.xmlcl.append
        # inputs then params in argparse named form

        for (k, v, koverride) in self.xclsuffix:
            if koverride > "":
                k = koverride
                aXCL(k)
            else:
                if len(k.strip()) == 1:
                    k = "-%s" % k
                else:
                    k = "--%s" % k
                aXCL(k)
                aXCL(v)
        for (k, v, koverride) in self.clsuffix:
            if koverride > "":
                k = koverride
            elif len(k.strip()) == 1:
                k = "-%s" % k
            else:
                k = "--%s" % k
            aCL(k)
            aCL(v)
        if self.lastxclredirect:
            aXCL(self.lastxclredirect[0])
            aXCL(self.lastxclredirect[1])
        if self.args.cl_user_suffix:  # DIY CL end
            clp = shlex.split(self.args.cl_user_suffix)
            for c in clp:
                aCL(c)
                aXCL(c)

    def getNdash(self, newname):
        if self.is_positional:
            ndash = 0
        else:
            ndash = 2
            if len(newname) < 2:
                ndash = 1
        return ndash

    def doXMLparam(self):  # noqa
        """Add all needed elements to tool"""
        for p in self.outfiles:
            newname = p["name"]
            newfmt = p["format"]
            newcl = p["CL"]
            test = p["test"]
            oldcl = p["origCL"]
            test = test.strip()
            ndash = self.getNdash(newcl)
            aparm = gxtp.OutputData(
                name=newname, format=newfmt, num_dashes=ndash, label=newname
            )
            aparm.positional = self.is_positional
            if self.is_positional:
                if oldcl.upper() == "STDOUT":
                    aparm.positional = 9999999
                    aparm.command_line_override = "> $%s" % newname
                else:
                    aparm.positional = int(oldcl)
                    aparm.command_line_override = "$%s" % newname
            self.toutputs.append(aparm)
            ld = None
            if test.strip() > "":
                if test.startswith("diff"):
                    c = "diff"
                    ld = 0
                    if test.split(":")[1].isdigit:
                        ld = int(test.split(":")[1])
                    tp = gxtp.TestOutput(
                        name=newname,
                        value="%s_sample" % newname,
                        compare=c,
                        lines_diff=ld,
                    )
                elif test.startswith("sim_size"):
                    c = "sim_size"
                    tn = test.split(":")[1].strip()
                    if tn > "":
                        if "." in tn:
                            delta = None
                            delta_frac = min(1.0, float(tn))
                        else:
                            delta = int(tn)
                            delta_frac = None
                    tp = gxtp.TestOutput(
                        name=newname,
                        value="%s_sample" % newname,
                        compare=c,
                        delta=delta,
                        delta_frac=delta_frac,
                    )
                else:
                    c = test
                    tp = gxtp.TestOutput(
                        name=newname,
                        value="%s_sample" % newname,
                        compare=c,
                    )
                self.testparam.append(tp)
        for p in self.infiles:
            newname = p["infilename"]
            newfmt = p["format"]
            ndash = self.getNdash(newname)
            reps = p.get("repeat", "0") == "1"
            if not len(p["label"]) > 0:
                alab = p["CL"]
            else:
                alab = p["label"]
            aninput = gxtp.DataParam(
                newname,
                optional=False,
                label=alab,
                help=p["help"],
                format=newfmt,
                multiple=False,
                num_dashes=ndash,
            )
            aninput.positional = self.is_positional
            if self.is_positional:
                if p["origCL"].upper() == "STDIN":
                    aninput.positional = 9999998
                    aninput.command_line_override = "> $%s" % newname
                else:
                    aninput.positional = int(p["origCL"])
                    aninput.command_line_override = "$%s" % newname
            if reps:
                repe = gxtp.Repeat(name=f"R_{newname}", title=f"Add as many {alab} as needed")
                repe.append(aninput)
                self.tinputs.append(repe)
                tparm = gxtp.TestRepeat(name=f"R_{newname}")
                tparm2 = gxtp.TestParam(newname, value="%s_sample" % newname)
                tparm.append(tparm2)
                self.testparam.append(tparm)
            else:
                self.tinputs.append(aninput)
                tparm = gxtp.TestParam(newname, value="%s_sample" % newname)
                self.testparam.append(tparm)
        for p in self.addpar:
            newname = p["name"]
            newval = p["value"]
            newlabel = p["label"]
            newhelp = p["help"]
            newtype = p["type"]
            newcl = p["CL"]
            oldcl = p["origCL"]
            reps = p["repeat"] == "1"
            if not len(newlabel) > 0:
                newlabel = newname
            ndash = self.getNdash(newname)
            if newtype == "text":
                aparm = gxtp.TextParam(
                    newname,
                    label=newlabel,
                    help=newhelp,
                    value=newval,
                    num_dashes=ndash,
                )
            elif newtype == "integer":
                aparm = gxtp.IntegerParam(
                    newname,
                    label=newlabel,
                    help=newhelp,
                    value=newval,
                    num_dashes=ndash,
                )
            elif newtype == "float":
                aparm = gxtp.FloatParam(
                    newname,
                    label=newlabel,
                    help=newhelp,
                    value=newval,
                    num_dashes=ndash,
                )
            elif newtype == "boolean":
                aparm = gxtp.BooleanParam(
                    newname,
                    label=newlabel,
                    help=newhelp,
                    value=newval,
                    num_dashes=ndash,
                )
            else:
                raise ValueError(
                    'Unrecognised parameter type "%s" for\
                 additional parameter %s in makeXML'
                    % (newtype, newname)
                )
            aparm.positional = self.is_positional
            if self.is_positional:
                aparm.positional = int(oldcl)
            if reps:
                repe = gxtp.Repeat(name=f"R_{newname}", title=f"Add as many {newlabel} as needed")
                repe.append(aparm)
                self.tinputs.append(repe)
                tparm = gxtp.TestRepeat(name=f"R_{newname}")
                tparm2 = gxtp.TestParam(newname, value=newval)
                tparm.append(tparm2)
                self.testparam.append(tparm)
            else:
                self.tinputs.append(aparm)
                tparm = gxtp.TestParam(newname, value=newval)
                self.testparam.append(tparm)
        for p in self.selpar:
            newname = p["name"]
            newval = p["value"]
            newlabel = p["label"]
            newhelp = p["help"]
            newtype = p["type"]
            newcl = p["CL"]
            if not len(newlabel) > 0:
                newlabel = newname
            ndash = self.getNdash(newname)
            if newtype == "selecttext":
                newtext = p["texts"]
                aparm = gxtp.SelectParam(
                    newname,
                    label=newlabel,
                    help=newhelp,
                    num_dashes=ndash,
                )
                for i in range(len(newval)):
                    anopt = gxtp.SelectOption(
                        value=newval[i],
                        text=newtext[i],
                    )
                    aparm.append(anopt)
                aparm.positional = self.is_positional
                if self.is_positional:
                    aparm.positional = int(newcl)
                self.tinputs.append(aparm)
                tparm = gxtp.TestParam(newname, value=newval)
                self.testparam.append(tparm)
            else:
                raise ValueError(
                    'Unrecognised parameter type "%s" for\
                 selecttext parameter %s in makeXML'
                    % (newtype, newname)
                )
        for p in self.collections:
            newkind = p["kind"]
            newname = p["name"]
            newlabel = p["label"]
            newdisc = p["discover"]
            collect = gxtp.OutputCollection(newname, label=newlabel, type=newkind)
            disc = gxtp.DiscoverDatasets(
                pattern=newdisc, directory=f"{newname}", visible="false"
            )
            collect.append(disc)
            self.toutputs.append(collect)
            try:
                tparm = gxtp.TestOutputCollection(newname)  # broken until PR merged.
                self.testparam.append(tparm)
            except Exception:
                print("#### WARNING: Galaxyxml version does not have the PR merged yet - tests for collections must be over-ridden until then!")

    def doNoXMLparam(self):
        """filter style package - stdin to stdout"""
        if len(self.infiles) > 0:
            alab = self.infiles[0]["label"]
            if len(alab) == 0:
                alab = self.infiles[0]["infilename"]
            max1s = (
                "Maximum one input if parampass is 0 but multiple input files supplied - %s"
                % str(self.infiles)
            )
            assert len(self.infiles) == 1, max1s
            newname = self.infiles[0]["infilename"]
            aninput = gxtp.DataParam(
                newname,
                optional=False,
                label=alab,
                help=self.infiles[0]["help"],
                format=self.infiles[0]["format"],
                multiple=False,
                num_dashes=0,
            )
            aninput.command_line_override = "< $%s" % newname
            aninput.positional = True
            self.tinputs.append(aninput)
            tp = gxtp.TestParam(name=newname, value="%s_sample" % newname)
            self.testparam.append(tp)
        if len(self.outfiles) > 0:
            newname = self.outfiles[0]["name"]
            newfmt = self.outfiles[0]["format"]
            anout = gxtp.OutputData(newname, format=newfmt, num_dashes=0)
            anout.command_line_override = "> $%s" % newname
            anout.positional = self.is_positional
            self.toutputs.append(anout)
            tp = gxtp.TestOutput(name=newname, value="%s_sample" % newname)
            self.testparam.append(tp)

    def makeXML(self):  # noqa
        """
        Create a Galaxy xml tool wrapper for the new script
        Uses galaxyhtml
        Hmmm. How to get the command line into correct order...
        """
        if self.command_override:
            self.newtool.command_override = self.command_override  # config file
        else:
            self.newtool.command_override = self.xmlcl
        cite = gxtp.Citations()
        acite = gxtp.Citation(type="doi", value="10.1093/bioinformatics/bts573")
        cite.append(acite)
        self.newtool.citations = cite
        safertext = ""
        if self.args.help_text:
            helptext = open(self.args.help_text, "r").readlines()
            safertext = "\n".join([cheetah_escape(x) for x in helptext])
        if len(safertext.strip()) == 0:
            safertext = (
                "Ask the tool author (%s) to rebuild with help text please\n"
                % (self.args.user_email)
            )
        if self.args.script_path:
            if len(safertext) > 0:
                safertext = safertext + "\n\n------\n"  # transition allowed!
            scr = [x for x in self.spacedScript if x.strip() > ""]
            scr.insert(0, "\n\nScript::\n")
            if len(scr) > 300:
                scr = (
                    scr[:100]
                    + ["    >300 lines - stuff deleted", "    ......"]
                    + scr[-100:]
                )
            scr.append("\n")
            safertext = safertext + "\n".join(scr)
        self.newtool.help = safertext
        self.newtool.version_command = f'echo "{self.args.tool_version}"'
        std = gxtp.Stdios()
        std1 = gxtp.Stdio()
        std.append(std1)
        self.newtool.stdios = std
        requirements = gxtp.Requirements()
        if self.args.packages:
            try:
                for d in self.args.packages.split(","):
                    ver = ""
                    d = d.replace("==", ":")
                    d = d.replace("=", ":")
                    if ":" in d:
                        packg, ver = d.split(":")
                    else:
                        packg = d
                    requirements.append(
                        gxtp.Requirement("package", packg.strip(), ver.strip())
                    )
            except Exception:
                print('### malformed packages string supplied - cannot parse =',self.args.packages)
                sys.exit(2)
        self.newtool.requirements = requirements
        if self.args.parampass == "0":
            self.doNoXMLparam()
        else:
            self.doXMLparam()
        self.newtool.outputs = self.toutputs
        self.newtool.inputs = self.tinputs
        if self.args.script_path:
            configfiles = gxtp.Configfiles()
            configfiles.append(
                gxtp.Configfile(name="runme", text="\n".join(self.escapedScript))
            )
            self.newtool.configfiles = configfiles
        tests = gxtp.Tests()
        test_a = gxtp.Test()
        for tp in self.testparam:
            test_a.append(tp)
        tests.append(test_a)
        self.newtool.tests = tests
        self.newtool.add_comment(
            "Created by %s at %s using the Galaxy Tool Factory."
            % (self.args.user_email, timenow())
        )
        self.newtool.add_comment("Source in git at: %s" % (toolFactoryURL))
        exml0 = self.newtool.export()
        exml = exml0.replace(FAKEEXE, "")  # temporary work around until PR accepted
        if (
            self.test_override
        ):  # cannot do this inside galaxyxml as it expects lxml objects for tests
            part1 = exml.split("<tests>")[0]
            part2 = exml.split("</tests>")[1]
            fixed = "%s\n%s\n%s" % (part1, "\n".join(self.test_override), part2)
            exml = fixed
        # exml = exml.replace('range="1:"', 'range="1000:"')
        xf = open("%s.xml" % self.tool_name, "w")
        xf.write(exml)
        xf.write("\n")
        xf.close()
        # ready for the tarball

    def run(self):  #noqa
        """
        generate test outputs by running a command line
        won't work if command or test override in play - planemo is the
        easiest way to generate test outputs for that case so is
        automagically selected
        """
        scl = " ".join(self.cl)
        err = None
        logname = f"{self.tool_name}_runner_log"
        if self.args.parampass != "0":
            if self.lastclredirect:
                logf = open(self.lastclredirect[1], "wb")  # is name of an output file
            else:
                logf = open(logname,'w')
                logf.write("No dependencies so sending CL = '%s' to the fast direct runner instead of planemo to generate tests" % scl)
            subp = subprocess.run(
                self.cl, shell=False, stdout=logf, stderr=logf
            )
            logf.close()
            retval = subp.returncode
        else:  # work around special case - stdin and write to stdout
            if len(self.infiles) > 0:
                sti = open(self.infiles[0]["name"], "rb")
            else:
                sti = sys.stdin
            if len(self.outfiles) > 0:
                sto = open(self.outfiles[0]["name"], "wb")
            else:
                sto = sys.stdout
            subp = subprocess.run(
                self.cl, shell=False, stdout=sto, stdin=sti
            )
            retval = subp.returncode
            sto.close()
            sti.close()
        if retval != 0 and err:  # problem
            sys.stderr.write(err)
        for p in self.outfiles:
            oname = p["name"]
            tdest = os.path.join(self.testdir, "%s_sample" % oname)
            if not os.path.isfile(tdest):
                if os.path.isfile(oname):
                    shutil.copyfile(oname, tdest)
                    dest = os.path.join(self.repdir, "%s.sample.%s" % (oname,p['format']))
                    shutil.copyfile(oname, dest)
                else:
                    if report_fail:
                        tout.write(
                            "###Tool may have failed - output file %s not found in testdir after planemo run %s."
                            % (oname, self.testdir)
                        )
        for p in self.infiles:
            pth = p["name"]
            dest = os.path.join(self.testdir, "%s_sample" % p["infilename"])
            shutil.copyfile(pth, dest)
            dest = os.path.join(self.repdir, "%s_sample.%s" % (p["infilename"],p["format"]))
            shutil.copyfile(pth, dest)
        with os.scandir('.') as outs:
            for entry in outs:
                newname = entry.name
                if not entry.is_file() or entry.name.endswith('_sample'):
                    continue
                if not (entry.name.endswith('.html') or entry.name.endswith('.gz') or entry.name.endswith(".tgz")):
                    fname, ext = os.path.splitext(entry.name)
                    if len(ext) > 1:
                        newname = f"{fname}_{ext[1:]}.txt"
                    else:
                        newname = f"{fname}.txt"
                dest = os.path.join(self.repdir, newname)
                src = entry.name
                shutil.copyfile(src, dest)
        return retval

    def writeShedyml(self):
        """for planemo"""
        yuser = self.args.user_email.split("@")[0]
        yfname = os.path.join(self.tooloutdir, ".shed.yml")
        yamlf = open(yfname, "w")
        odict = {
            "name": self.tool_name,
            "owner": yuser,
            "type": "unrestricted",
            "description": self.args.tool_desc,
            "synopsis": self.args.tool_desc,
            "category": "TF Generated Tools",
        }
        yaml.dump(odict, yamlf, allow_unicode=True)
        yamlf.close()

    def makeTool(self):
        """write xmls and input samples into place"""
        if self.args.parampass == 0:
            self.doNoXMLparam()
        else:
            self.makeXML()
        if self.args.script_path:
            stname = os.path.join(self.tooloutdir, self.sfile)
            if not os.path.exists(stname):
                shutil.copyfile(self.sfile, stname)
        xreal = "%s.xml" % self.tool_name
        xout = os.path.join(self.tooloutdir, xreal)
        shutil.copyfile(xreal, xout)
        for p in self.infiles:
            pth = p["name"]
            dest = os.path.join(self.testdir, "%s_sample" % p["infilename"])
            shutil.copyfile(pth, dest)
            dest = os.path.join(self.repdir, "%s_sample.%s" % (p["infilename"],p["format"]))
            shutil.copyfile(pth, dest)

    def makeToolTar(self, report_fail=False):
        """move outputs into test-data and prepare the tarball"""
        excludeme = "_planemo_test_report.html"

        def exclude_function(tarinfo):
            filename = tarinfo.name
            return None if filename.endswith(excludeme) else tarinfo

        for p in self.outfiles:
            oname = p["name"]
            tdest = os.path.join(self.testdir, "%s_sample" % oname)
            src = os.path.join(self.testdir, oname)
            if not os.path.isfile(tdest):
                if os.path.isfile(src):
                    shutil.copyfile(src, tdest)
                    dest = os.path.join(self.repdir, "%s.sample" % (oname))
                    shutil.copyfile(src, dest)
                else:
                    if report_fail:
                        print(
                            "###Tool may have failed - output file %s not found in testdir after planemo run %s."
                            % (tdest, self.testdir)
                        )
        tf = tarfile.open(self.newtarpath, "w:gz")
        tf.add(
            name=self.tooloutdir,
            arcname=self.tool_name,
            filter=exclude_function,
        )
        tf.close()
        shutil.copyfile(self.newtarpath, self.args.new_tool)

    def moveRunOutputs(self):
        """need to move planemo or run outputs into toolfactory collection"""
        with os.scandir(self.tooloutdir) as outs:
            for entry in outs:
                if not entry.is_file():
                    continue
                if not entry.name.endswith('.html'):
                    _, ext = os.path.splitext(entry.name)
                    newname = f"{entry.name.replace('.','_')}.txt"
                dest = os.path.join(self.repdir, newname)
                src = os.path.join(self.tooloutdir, entry.name)
                shutil.copyfile(src, dest)
        if self.args.include_tests:
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


def main():
    """
    This is a Galaxy wrapper.
    It expects to be called by a special purpose tool.xml

    """
    parser = argparse.ArgumentParser()
    a = parser.add_argument
    a("--script_path", default=None)
    a("--history_test", default=None)
    a("--cl_user_suffix", default=None)
    a("--sysexe", default=None)
    a("--packages", default=None)
    a("--tool_name", default="newtool")
    a("--tool_dir", default=None)
    a("--input_files", default=[], action="append")
    a("--output_files", default=[], action="append")
    a("--user_email", default="Unknown")
    a("--bad_user", default=None)
    a("--help_text", default=None)
    a("--tool_desc", default=None)
    a("--tool_version", default=None)
    a("--citations", default=None)
    a("--command_override", default=None)
    a("--test_override", default=None)
    a("--additional_parameters", action="append", default=[])
    a("--selecttext_parameters", action="append", default=[])
    a("--edit_additional_parameters", action="store_true", default=False)
    a("--parampass", default="positional")
    a("--tfout", default="./tfout")
    a("--new_tool", default="new_tool")
    a("--galaxy_root", default="/galaxy-central")
    a("--galaxy_venv", default="/galaxy_venv")
    a("--collection", action="append", default=[])
    a("--include_tests", default=False, action="store_true")
    a("--install", default=False, action="store_true")
    a("--run_test", default=False, action="store_true")
    a("--local_tools", default='tools') # relative to galaxy_root
    a("--tool_conf_path", default='/galaxy_root/config/tool_conf.xml')
    a("--galaxy_url", default="http://localhost:8080")
    a("--toolshed_url", default="http://localhost:9009")
    # make sure this is identical to tool_sheds_conf.xml
    # localhost != 127.0.0.1 so validation fails
    a("--toolshed_api_key", default="fakekey")
    a("--galaxy_api_key", default="8993d65865e6d6d1773c2c34a1cc207d")
    args = parser.parse_args()
    assert not args.bad_user, (
        'UNAUTHORISED: %s is NOT authorized to use this tool until Galaxy \
admin adds %s to "admin_users" in the galaxy.yml Galaxy configuration file'
        % (args.bad_user, args.bad_user)
    )
    assert args.tool_name, "## Tool Factory expects a tool name - eg --tool_name=DESeq"
    assert (
        args.sysexe or args.packages
    ), "## Tool Factory wrapper expects an interpreter \
or an executable package in --sysexe or --packages"
    print('Hello from',os.getcwd())
    r = ScriptRunner(args)
    r.writeShedyml()
    r.makeTool()
    r.makeToolTar()
    if args.run_test:
        if not args.packages or args.packages.strip() == "bash":
            r.run()
            r.makeToolTar()
        else:
            tt = ToolTester(report_dir=r.repdir, in_tool_archive=r.newtarpath, new_tool_archive=r.args.new_tool, galaxy_root=args.galaxy_root, include_tests=False)
    if args.install:
        #try:
        tcu = ToolConfUpdater(args=args, tool_dir=os.path.join(args.galaxy_root,args.local_tools),
        new_tool_archive_path=r.newtarpath, tool_conf_path=os.path.join(args.galaxy_root,'config','tool_conf.xml'),
        new_tool_name=r.tool_name)
        #except Exception:
        #   print("### Unable to install the new tool. Are you sure you have all the required special settings?")

if __name__ == "__main__":
    main()

