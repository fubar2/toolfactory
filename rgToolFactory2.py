# replace with shebang for biocontainer
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


import galaxyxml.tool as gxt
import galaxyxml.tool.parameters as gxtp
import lxml
import yaml
from bioblend import ConnectionError
from bioblend import toolshed


myversion = "V2.2 February 2021"
verbose = True
debug = True
toolFactoryURL = "https://github.com/fubar2/toolfactory"
foo = len(lxml.__version__)
# fug you, flake8. Say my name!
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


class ScriptRunner:
    """Wrapper for an arbitrary script
    uses galaxyxml

    """

    def __init__(self, args=None):
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
        self.repdir = "./TF_run_report_tempdir"
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

        self.elog = os.path.join(self.repdir, "%s_error_log.txt" % self.tool_name)
        self.tlog = os.path.join(self.repdir, "%s_runner_log.txt" % self.tool_name)
        if self.args.parampass == "0":
            self.clsimple()
        else:
            if self.args.parampass == "positional":
                self.prepclpos()
                self.clpositional()
            else:
                self.prepargp()
                self.clargparse()
        if self.args.cl_suffix:  # DIY CL end
            clp = shlex.split(self.args.cl_suffix)
            for c in clp:
                aCL(c)
                aXCL(c)

    def clsimple(self):
        """no parameters - uses < and > for i/o"""
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

    def prepargp(self):
        clsuffix = []
        xclsuffix = []
        for i, p in enumerate(self.infiles):
            if p["origCL"].strip().upper() == "STDIN":
                appendme = [
                    p["infilename"],
                    p["infilename"],
                    "< %s" % p["infilename"],
                ]
                xappendme = [
                    p["infilename"],
                    p["infilename"],
                    "< $%s" % p["infilename"],
                ]
            else:
                appendme = [p["CL"], p["CL"], ""]
                xappendme = [p["CL"], "$%s" % p["CL"], ""]
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
            clsuffix.append([p["CL"], p["name"], p["override"]])
            xclsuffix.append([p["CL"], '"$%s"' % p["name"], p["override"]])
        for p in self.selpar:
            clsuffix.append([p["CL"], p["name"], p["override"]])
            xclsuffix.append([p["CL"], '"$%s"' % p["name"], p["override"]])
        clsuffix.sort()
        xclsuffix.sort()
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
            clsuffix.append([p["CL"], p["name"], p["override"]])
            xclsuffix.append([p["CL"], '"$%s"' % p["name"], p["override"]])
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
        self.escapedScript = [cheetah_escape(x) for x in rx]
        self.spacedScript = [f"    {x}" for x in rx if x.strip() > ""]
        art = "%s.%s" % (self.tool_name, self.executeme[0])
        artifact = open(art, "wb")
        artifact.write(bytes("\n".join(self.escapedScript), "utf8"))
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

    def clargparse(self):
        """argparse style"""
        aCL = self.cl.append
        aXCL = self.xmlcl.append
        # inputs then params in argparse named form

        for (k, v, koverride) in self.xclsuffix:
            if koverride > "":
                k = koverride
            elif len(k.strip()) == 1:
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

    def getNdash(self, newname):
        if self.is_positional:
            ndash = 0
        else:
            ndash = 2
            if len(newname) < 2:
                ndash = 1
        return ndash

    def doXMLparam(self):
        """flake8 made me do this..."""
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
            self.tinputs.append(aninput)
            tparm = gxtp.TestParam(name=newname, value="%s_sample" % newname)
            self.testparam.append(tparm)
        for p in self.addpar:
            newname = p["name"]
            newval = p["value"]
            newlabel = p["label"]
            newhelp = p["help"]
            newtype = p["type"]
            newcl = p["CL"]
            oldcl = p["origCL"]
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
            tparm = gxtp.TestOutputCollection(newname)
            self.testparam.append(tparm)

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

    def makeXML(self):
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
        requirements = gxtp.Requirements()
        if self.args.packages:
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

    def run(self):
        """
        generate test outputs by running a command line
        won't work if command or test override in play - planemo is the
        easiest way to generate test outputs for that case so is
        automagically selected
        """
        scl = " ".join(self.cl)
        err = None
        if self.args.parampass != "0":
            if os.path.exists(self.elog):
                ste = open(self.elog, "a")
            else:
                ste = open(self.elog, "w")
            if self.lastclredirect:
                sto = open(self.lastclredirect[1], "wb")  # is name of an output file
            else:
                if os.path.exists(self.tlog):
                    sto = open(self.tlog, "a")
                else:
                    sto = open(self.tlog, "w")
                sto.write(
                    "## Executing Toolfactory generated command line = %s\n" % scl
                )
            sto.flush()
            subp = subprocess.run(
                self.cl, shell=False, stdout=sto, stderr=ste
            )
            sto.close()
            ste.close()
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
            sto.write("## Executing Toolfactory generated command line = %s\n" % scl)
            retval = subp.returncode
            sto.close()
            sti.close()
        if os.path.isfile(self.tlog) and os.stat(self.tlog).st_size == 0:
            os.unlink(self.tlog)
        if os.path.isfile(self.elog) and os.stat(self.elog).st_size == 0:
            os.unlink(self.elog)
        if retval != 0 and err:  # problem
            sys.stderr.write(err)
        logging.debug("run done")
        return retval

    def shedLoad(self):
        """
        use bioblend to create new repository
        or update existing

        """
        if os.path.exists(self.tlog):
            sto = open(self.tlog, "a")
        else:
            sto = open(self.tlog, "w")

        ts = toolshed.ToolShedInstance(
            url=self.args.toolshed_url,
            key=self.args.toolshed_api_key,
            verify=False,
        )
        repos = ts.repositories.get_repositories()
        rnames = [x.get("name", "?") for x in repos]
        rids = [x.get("id", "?") for x in repos]
        tfcat = "ToolFactory generated tools"
        if self.tool_name not in rnames:
            tscat = ts.categories.get_categories()
            cnames = [x.get("name", "?").strip() for x in tscat]
            cids = [x.get("id", "?") for x in tscat]
            catID = None
            if tfcat.strip() in cnames:
                ci = cnames.index(tfcat)
                catID = cids[ci]
            res = ts.repositories.create_repository(
                name=self.args.tool_name,
                synopsis="Synopsis:%s" % self.args.tool_desc,
                description=self.args.tool_desc,
                type="unrestricted",
                remote_repository_url=self.args.toolshed_url,
                homepage_url=None,
                category_ids=catID,
            )
            tid = res.get("id", None)
            sto.write(f"#create_repository {self.args.tool_name} tid={tid} res={res}\n")
        else:
            i = rnames.index(self.tool_name)
            tid = rids[i]
        try:
            res = ts.repositories.update_repository(
                id=tid, tar_ball_path=self.newtarpath, commit_message=None
            )
            sto.write(f"#update res id {id} ={res}\n")
        except ConnectionError:
            sto.write(
                "####### Is the toolshed running and the API key correct? Bioblend shed upload failed\n"
            )
        sto.close()

    def eph_galaxy_load(self):
        """
        use ephemeris to load the new tool from the local toolshed after planemo uploads it
        """
        if os.path.exists(self.tlog):
            tout = open(self.tlog, "a")
        else:
            tout = open(self.tlog, "w")
        cll = [
            "shed-tools",
            "install",
            "-g",
            self.args.galaxy_url,
            "--latest",
            "-a",
            self.args.galaxy_api_key,
            "--name",
            self.tool_name,
            "--owner",
            "fubar",
            "--toolshed",
            self.args.toolshed_url,
            "--section_label",
            "ToolFactory",
        ]
        tout.write("running\n%s\n" % " ".join(cll))
        subp = subprocess.run(
            cll,
            cwd=self.ourcwd,
            shell=False,
            stderr=tout,
            stdout=tout,
        )
        tout.write(
            "installed %s - got retcode %d\n" % (self.tool_name, subp.returncode)
        )
        tout.close()
        return subp.returncode

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
            dest = os.path.join(self.repdir, "%s_sample" % p["infilename"])
            shutil.copyfile(pth, dest)

    def makeToolTar(self, report_fail=False):
        """move outputs into test-data and prepare the tarball"""
        excludeme = "_planemo_test_report.html"

        def exclude_function(tarinfo):
            filename = tarinfo.name
            return None if filename.endswith(excludeme) else tarinfo

        if os.path.exists(self.tlog):
            tout = open(self.tlog, "a")
        else:
            tout = open(self.tlog, "w")
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
                        tout.write(
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

    def planemo_test_once(self):
        """planemo is a requirement so is available for testing but needs a
        different call if in the biocontainer - see above
        and for generating test outputs if command or test overrides are
        supplied test outputs are sent to repdir for display
        """
        xreal = "%s.xml" % self.tool_name
        tool_test_path = os.path.join(
            self.repdir, f"{self.tool_name}_planemo_test_report.html"
        )
        if os.path.exists(self.tlog):
            tout = open(self.tlog, "a")
        else:
            tout = open(self.tlog, "w")
        cll = [
            "planemo",
            "test",
            "--conda_auto_init",
            "--test_data",
            os.path.abspath(self.testdir),
            "--test_output",
            os.path.abspath(tool_test_path),
            "--galaxy_root",
            self.args.galaxy_root,
            "--update_test_data",
            os.path.abspath(xreal),
        ]
        p = subprocess.run(
            cll,
            shell=False,
            cwd=self.tooloutdir,
            stderr=tout,
            stdout=tout,
        )
        tout.close()
        return p.returncode


def main():
    """
    This is a Galaxy wrapper.
    It expects to be called by a special purpose tool.xml

    """
    parser = argparse.ArgumentParser()
    a = parser.add_argument
    a("--script_path", default=None)
    a("--history_test", default=None)
    a("--cl_suffix", default=None)
    a("--sysexe", default=None)
    a("--packages", default=None)
    a("--tool_name", default="newtool")
    a("--tool_dir", default=None)
    a("--input_files", default=[], action="append")
    a("--output_files", default=[], action="append")
    a("--user_email", default="Unknown")
    a("--bad_user", default=None)
    a("--make_Tool", default="runonly")
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
    a("--galaxy_url", default="http://localhost:8080")
    a("--toolshed_url", default="http://localhost:9009")
    # make sure this is identical to tool_sheds_conf.xml
    # localhost != 127.0.0.1 so validation fails
    a("--toolshed_api_key", default="fakekey")
    a("--galaxy_api_key", default="fakekey")
    a("--galaxy_root", default="/galaxy-central")
    a("--galaxy_venv", default="/galaxy_venv")
    a("--collection", action="append", default=[])
    a("--include_tests", default=False, action="store_true")
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
    r = ScriptRunner(args)
    r.writeShedyml()
    r.makeTool()
    if args.make_Tool == "generate":
        r.run()
        r.moveRunOutputs()
        r.makeToolTar()
    else:
        # r.planemo_test(genoutputs=True)  # this fails :( - see PR
        # r.moveRunOutputs()
        # r.makeToolTar(report_fail=False)
        r.planemo_test_once()
        r.moveRunOutputs()
        r.makeToolTar(report_fail=True)
        if args.make_Tool == "gentestinstall":
            r.shedLoad()
            r.eph_galaxy_load()


if __name__ == "__main__":
    main()
