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
#
# uses planemo in a biodocker sort of image as a requirement
# otherwise planemo seems to leak dependencies back into the
# calling venv. Hilarity ensues.



import argparse
import copy
import datetime
import grp
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time


from bioblend import ConnectionError
from bioblend import toolshed


import galaxyxml.tool as gxt
import galaxyxml.tool.parameters as gxtp

import lxml

import yaml

myversion = "V2.1 July 2020"
verbose = True
debug = True
toolFactoryURL = "https://github.com/fubar2/toolfactory"
ourdelim = "~~~"

# --input_files="$intab.input_files~~~$intab.input_CL~~~$intab.input_formats\
#~~~$intab.input_label~~~$intab.input_help"
IPATHPOS = 0
ICLPOS = 1
IFMTPOS = 2
ILABPOS = 3
IHELPOS = 4
IOCLPOS = 5

# --output_files "$otab.history_name~~~$otab.history_format~~~$otab.history_CL~~~$otab.history_test"
ONAMEPOS = 0
OFMTPOS = 1
OCLPOS = 2
OTESTPOS = 3
OOCLPOS = 4


# --additional_parameters="$i.param_name~~~$i.param_value~~~
# $i.param_label~~~$i.param_help~~~$i.param_type~~~$i.CL~~~i$.param_CLoverride"
ANAMEPOS = 0
AVALPOS = 1
ALABPOS = 2
AHELPPOS = 3
ATYPEPOS = 4
ACLPOS = 5
AOVERPOS = 6
AOCLPOS = 7


foo = len(lxml.__version__)
# fug you, flake8. Say my name!
FAKEEXE = "~~~REMOVE~~~ME~~~"
# need this until a PR/version bump to fix galaxyxml prepending the exe even
# with override.


def timenow():
    """return current time as a string"""
    return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(time.time()))


def quote_non_numeric(s):
    """return a prequoted string for non-numerics
    useful for perl and Rscript parameter passing?
    """
    try:
        _ = float(s)
        return s
    except ValueError:
        return '"%s"' % s


html_escape_table = {"&": "&amp;", ">": "&gt;", "<": "&lt;", "$": r"\$","#":"&#35;", "$":"&#36;"}
cheetah_escape_table = {"$": "\$","#":"\#"}

def html_escape(text):
    """Produce entities within text."""
    return "".join([html_escape_table.get(c, c) for c in text])

def cheetah_escape(text):
    """Produce entities within text."""
    return "".join([cheetah_escape_table.get(c, c) for c in text])


def html_unescape(text):
    """Revert entities within text. Multiple character targets so use replace"""
    t = text.replace("&amp;", "&")
    t = t.replace("&gt;", ">")
    t = t.replace("&lt;", "<")
    t = t.replace("\\$", "$")
    t = t.replace("&#36;","$")
    t = t.replace("&#35;","#")
    return t


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
        self.ourenv = copy.deepcopy(os.environ)
        self.infiles = [x.split(ourdelim) for x in args.input_files]
        self.outfiles = [x.split(ourdelim) for x in args.output_files]
        self.addpar = [x.split(ourdelim) for x in args.additional_parameters]
        self.args = args
        self.cleanuppar()
        self.lastclredirect = None
        self.lastxclredirect = None
        self.cl = []
        self.xmlcl = []
        self.is_positional = self.args.parampass == "positional"
        if self.args.sysexe:
            self.executeme = self.args.sysexe
        else:
            if self.args.packages:
                self.executeme = self.args.packages.split(",")[0].split(":")[0]
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
        self.newtarpath = "toolfactory_%s.tgz" % self.tool_name
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
        if self.args.cl_prefix:  # DIY CL start
            clp = self.args.cl_prefix.split(" ")
            for c in clp:
                aCL(c)
                aXCL(c)
        else:
            if self.args.script_path:
                aCL(self.executeme)
                aCL(self.sfile)
                aXCL(self.executeme)
                aXCL("$runme")
            else:
                aCL(self.executeme)
                aXCL(self.executeme)
        self.elog = os.path.join(self.repdir, "%s_error_log.txt" % self.tool_name)
        self.tlog = os.path.join(self.repdir, "%s_runner_log.txt" % self.tool_name)

        if self.args.parampass == "0":
            self.clsimple()
        else:
            clsuffix = []
            xclsuffix = []
            for i, p in enumerate(self.infiles):
                if p[IOCLPOS] == "STDIN":
                    appendme = [
                        p[IOCLPOS],
                        p[ICLPOS],
                        p[IPATHPOS],
                        "< %s" % p[IPATHPOS],
                    ]
                    xappendme = [
                        p[IOCLPOS],
                        p[ICLPOS],
                        p[IPATHPOS],
                        "< $%s" % p[ICLPOS],
                    ]
                else:
                    appendme = [p[IOCLPOS], p[ICLPOS], p[IPATHPOS], ""]
                    xappendme = [p[IOCLPOS], p[ICLPOS], "$%s" % p[ICLPOS], ""]
                clsuffix.append(appendme)
                xclsuffix.append(xappendme)
            for i, p in enumerate(self.outfiles):
                if p[OOCLPOS] == "STDOUT":
                    self.lastclredirect = [">", p[ONAMEPOS]]
                    self.lastxclredirect = [">", "$%s" % p[OCLPOS]]
                else:
                    clsuffix.append([p[ONAMEPOS], p[ONAMEPOS], p[ONAMEPOS], ""])
                    xclsuffix.append([p[ONAMEPOS], p[ONAMEPOS], "$%s" % p[ONAMEPOS], ""])
            for p in self.addpar:
                clsuffix.append([p[AOCLPOS], p[ACLPOS], p[AVALPOS], p[AOVERPOS]])
                xclsuffix.append(
                    [p[AOCLPOS], p[ACLPOS], '"$%s"' % p[ANAMEPOS], p[AOVERPOS]]
                )
            clsuffix.sort()
            xclsuffix.sort()
            self.xclsuffix = xclsuffix
            self.clsuffix = clsuffix
            if self.args.parampass == "positional":
                self.clpositional()
            else:
                self.clargparse()

    def prepScript(self):
        rx = open(self.args.script_path, "r").readlines()
        rx = [x.rstrip() for x in rx]
        rxcheck = [x.strip() for x in rx if x.strip() > ""]
        assert len(rxcheck) > 0, "Supplied script is empty. Cannot run"
        self.script = "\n".join(rx)
        fhandle, self.sfile = tempfile.mkstemp(
            prefix=self.tool_name, suffix="_%s" % (self.executeme)
        )
        tscript = open(self.sfile, "w")
        tscript.write(self.script)
        tscript.close()
        self.escapedScript = [cheetah_escape(x) for x in rx]
        self.spacedScript = [f"    {x}" for x in rx if x.strip() > ""]
        art = "%s.%s" % (self.tool_name, self.executeme)
        artifact = open(art, "wb")
        artifact.write(bytes('\n'.join(self.escapedScript),'utf8'))
        artifact.close()

    def cleanuppar(self):
        """ positional parameters are complicated by their numeric ordinal"""
        for i, p in enumerate(self.infiles):
            infp = copy.copy(p)
            if self.args.parampass == "positional":
                assert infp[
                    ICLPOS
                ].isdigit(), "Positional parameters must be ordinal integers - got %s for %s" % (
                    infp[ICLPOS],
                    infp[ILABPOS],
                )
            icl = infp[ICLPOS]
            infp.append(icl)
            if infp[ICLPOS].isdigit() or self.args.parampass == "0":
                scl = "input%d" % (i + 1)
                infp[ICLPOS] = scl
            self.infiles[i] = infp
        for i, p in enumerate(
            self.outfiles
        ):
            if self.args.parampass == "positional" and p[OCLPOS].upper() != "STDOUT":
                assert p[
                    OCLPOS
                ].isdigit(), "Positional parameters must be ordinal integers - got %s for %s" % (
                    p[OCLPOS],
                    p[ONAMEPOS],
                )
            p.append(p[OCLPOS]) # keep copy
            if p[OOCLPOS].isdigit() or p[OOCLPOS].upper() == "STDOUT":
                scl = p[ONAMEPOS]
                p[OCLPOS] = scl
            self.outfiles[i] = p
        for i, p in enumerate(self.addpar):
            if self.args.parampass == "positional":
                assert p[
                    ACLPOS
                ].isdigit(), "Positional parameters must be ordinal integers - got %s for %s" % (
                    p[ACLPOS],
                    p[ANAMEPOS],
                )
            p.append(p[ACLPOS])
            if p[ACLPOS].isdigit():
                scl = "input%s" % p[ACLPOS]
                p[ACLPOS] = scl
            self.addpar[i] = p

    def clsimple(self):
        """no parameters - uses < and > for i/o"""
        aCL = self.cl.append
        aXCL = self.xmlcl.append

        if len(self.infiles) > 0:
            aCL("<")
            aCL(self.infiles[0][IPATHPOS])
            aXCL("<")
            aXCL("$%s" % self.infiles[0][ICLPOS])
        if len(self.outfiles) > 0:
            aCL(">")
            aCL(self.outfiles[0][OCLPOS])
            aXCL(">")
            aXCL("$%s" % self.outfiles[0][ONAMEPOS])

    def clpositional(self):
        # inputs in order then params
        aCL = self.cl.append
        for (o_v, k, v, koverride) in self.clsuffix:
            if " " in v:
                aCL("%s" % v)
            else:
                aCL(v)
        aXCL = self.xmlcl.append
        for (o_v, k, v, koverride) in self.xclsuffix:
            aXCL(v)
        if self.lastxclredirect:
            aXCL(self.lastxclredirect[0])
            aXCL(self.lastxclredirect[1])


    def clargparse(self):
        """argparse style"""
        aCL = self.cl.append
        aXCL = self.xmlcl.append
        # inputs then params in argparse named form

        for (o_v, k, v, koverride) in self.xclsuffix:
            if koverride > "":
                k = koverride
            elif len(k.strip()) == 1:
                k = "-%s" % k
            else:
                k = "--%s" % k
            aXCL(k)
            aXCL(v)
        for (o_v, k, v, koverride) in self.clsuffix:
            if koverride > "":
                k = koverride
            elif len(k.strip()) == 1:
                k = "-%s" % k
            else:
                k = "--%s" % k
            aCL(k)
            aCL(v)


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
        for p in self.outfiles: # --output_files "$otab.history_name~~~$otab.history_format~~~$otab.history_CL~~~$otab.history_test"
            newname, newfmt, newcl, test, oldcl = p
            test = test.strip()
            ndash = self.getNdash(newcl)
            aparm = gxtp.OutputData(name=newname, format=newfmt, num_dashes=ndash, label=newcl)
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
                                    name=newcl,
                                    value="%s_sample" % newcl,
                                    format=newfmt,
                                    compare= c,
                                    lines_diff=ld,
                                )
                elif test.startswith("sim_size"):
                    c = "sim_size"
                    tn = test.split(":")[1].strip()
                    if tn > '':
                        if '.' in tn:
                            delta = None
                            delta_frac = min(1.0,float(tn))
                        else:
                            delta = int(tn)
                            delta_frac = None
                    tp = gxtp.TestOutput(
                                    name=newcl,
                                    value="%s_sample" % newcl,
                                    format=newfmt,
                                    compare= c,
                                    delta = delta,
                                    delta_frac = delta_frac
                                )
                self.testparam.append(tp)
        for p in self.infiles:
            newname = p[ICLPOS]
            newfmt = p[IFMTPOS]
            ndash = self.getNdash(newname)
            if not len(p[ILABPOS]) > 0:
                alab = p[ICLPOS]
            else:
                alab = p[ILABPOS]
            aninput = gxtp.DataParam(
                newname,
                optional=False,
                label=alab,
                help=p[IHELPOS],
                format=newfmt,
                multiple=False,
                num_dashes=ndash,
            )
            aninput.positional = self.is_positional
            self.tinputs.append(aninput)
            tparm = gxtp.TestParam(name=newname, value="%s_sample" % newname)
            self.testparam.append(tparm)
        for p in self.addpar:
            newname, newval, newlabel, newhelp, newtype, newcl, override, oldcl = p
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
                    label=newname,
                    help=newhelp,
                    value=newval,
                    num_dashes=ndash,
                )
            elif newtype == "float":
                aparm = gxtp.FloatParam(
                    newname,
                    label=newname,
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

    def doNoXMLparam(self):
        """filter style package - stdin to stdout"""
        if len(self.infiles) > 0:
            alab = self.infiles[0][ILABPOS]
            if len(alab) == 0:
                alab = self.infiles[0][ICLPOS]
            max1s = (
                "Maximum one input if parampass is 0 but multiple input files supplied - %s"
                % str(self.infiles)
            )
            assert len(self.infiles) == 1, max1s
            newname = self.infiles[0][ICLPOS]
            aninput = gxtp.DataParam(
                newname,
                optional=False,
                label=alab,
                help=self.infiles[0][IHELPOS],
                format=self.infiles[0][IFMTPOS],
                multiple=False,
                num_dashes=0,
            )
            aninput.command_line_override = "< $%s" % newname
            aninput.positional = self.is_positional
            self.tinputs.append(aninput)
            tp = gxtp.TestParam(name=newname, value="%s_sample" % newname)
            self.testparam.append(tp)
        if len(self.outfiles) > 0:
            newname = self.outfiles[0][OCLPOS]
            newfmt = self.outfiles[0][OFMTPOS]
            anout = gxtp.OutputData(newname, format=newfmt, num_dashes=0)
            anout.command_line_override = "> $%s" % newname
            anout.positional = self.is_positional
            self.toutputs.append(anout)
            tp = gxtp.TestOutput(
                name=newname, value="%s_sample" % newname, format=newfmt
            )
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
        if self.args.help_text:
            helptext = open(self.args.help_text, "r").readlines()
            safertext = "\n".join([cheetah_escape(x) for x in helptext])
            if self.args.script_path:
                scr = [x for x in self.spacedScript if x.strip() > ""]
                scr.insert(0,'\n------\n\n\nScript::\n')
                if len(scr) > 300:
                    scr = (
                        scr[:100]
                        + ["    >300 lines - stuff deleted", "    ......"]
                        + scr[-100:]
                    )
                scr.append('\n')
                safertext = safertext + "\n".join(scr)
            self.newtool.help = safertext
        else:
            self.newtool.help = (
                "Please ask the tool author (%s) for help \
              as none was supplied at tool generation\n"
                % (self.args.user_email)
            )
        self.newtool.version_command = None  # do not want
        requirements = gxtp.Requirements()
        if self.args.packages:
            for d in self.args.packages.split(","):
                ver = ''
                d = d.replace('==',':')
                d = d.replace('=',':')
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
            configfiles.append(gxtp.Configfile(name="runme", text="\n".join(self.escapedScript)))
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
        self.newtool.add_comment(
            "Cite: Creating re-usable tools from scripts doi:10.1093/bioinformatics/bts573"
        )
        exml0 = self.newtool.export()
        exml = exml0.replace(FAKEEXE, "")  # temporary work around until PR accepted
        if (
            self.test_override
        ):  # cannot do this inside galaxyxml as it expects lxml objects for tests
            part1 = exml.split("<tests>")[0]
            part2 = exml.split("</tests>")[1]
            fixed = "%s\n%s\n%s" % (part1, self.test_override, part2)
            exml = fixed
        #exml = exml.replace('range="1:"', 'range="1000:"')
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
                self.cl, env=self.ourenv, shell=False, stdout=sto, stderr=ste
            )
            sto.close()
            ste.close()
            retval = subp.returncode
        else:  # work around special case - stdin and write to stdout
            if len(self.infiles) > 0:
                sti = open(self.infiles[0][IPATHPOS], "rb")
            else:
                sti = sys.stdin
            if len(self.outfiles) > 0:
                sto = open(self.outfiles[0][ONAMEPOS], "wb")
            else:
                sto = sys.stdout
            subp = subprocess.run(
                self.cl, env=self.ourenv, shell=False, stdout=sto, stdin=sti
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

    def copy_to_container(self, src, dest, container):
        """Recreate the src directory tree at dest - full path included"""
        idir = os.getcwd()
        workdir = os.path.dirname(src)
        os.chdir(workdir)
        _, tfname = tempfile.mkstemp(suffix=".tar")
        tar = tarfile.open(tfname, mode="w")
        srcb = os.path.basename(src)
        tar.add(srcb)
        tar.close()
        data = open(tfname, "rb").read()
        container.put_archive(dest, data)
        os.unlink(tfname)
        os.chdir(idir)

    def copy_from_container(self, src, dest, container):
        """recreate the src directory tree at dest using docker sdk"""
        os.makedirs(dest, exist_ok=True)
        _, tfname = tempfile.mkstemp(suffix=".tar")
        tf = open(tfname, "wb")
        bits, stat = container.get_archive(src)
        for chunk in bits:
            tf.write(chunk)
        tf.close()
        tar = tarfile.open(tfname, "r")
        tar.extractall(dest)
        tar.close()
        os.unlink(tfname)

    def planemo_biodocker_test(self):
        """
        planemo currently leaks dependencies if used in the same container and gets unhappy after a
        first successful run. https://github.com/galaxyproject/planemo/issues/1078#issuecomment-731476930

        Docker biocontainer has planemo with caches filled to save repeated downloads


        """

        def prun(container, tout, cl, user="biodocker"):
            rlog = container.exec_run(cl, user=user)
            slogl = str(rlog).split("\\n")
            slog = "\n".join(slogl)
            tout.write(f"## got rlog {slog} from {cl}\n")

        if os.path.exists(self.tlog):
            tout = open(self.tlog, "a")
        else:
            tout = open(self.tlog, "w")
        planemoimage = "quay.io/fubar2/planemo-biocontainer"
        xreal = "%s.xml" % self.tool_name
        repname = f"{self.tool_name}_planemo_test_report.html"
        ptestrep_path = os.path.join(self.repdir, repname)
        tool_name = self.tool_name
        client = docker.from_env()
        tvol = client.volumes.create()
        tvolname = tvol.name
        destdir = "/toolfactory/ptest"
        imrep = os.path.join(destdir, repname)
        # need to keep the container running so keep it open with sleep
        # will stop and destroy it when we are done
        container = client.containers.run(
            planemoimage,
            "sleep 120m",
            detach=True,
            user="biodocker",
            volumes={f"{tvolname}": {"bind": "/toolfactory", "mode": "rw"}},
        )
        cl = f"mkdir -p {destdir}"
        prun(container, tout, cl, user="root")
        # that's how hard it is to get root on a biodocker container :(
        cl = f"rm -rf {destdir}/*"
        prun(container, tout, cl, user="root")
        ptestpath = os.path.join(destdir, "tfout", xreal)
        self.copy_to_container(self.tooloutdir, destdir, container)
        cl = "chown -R biodocker /toolfactory"
        prun(container, tout, cl, user="root")
        rlog = container.exec_run(f"ls -la {destdir}")
        ptestcl = f"planemo test  --update_test_data  --no_cleanup --test_data {destdir}/tfout/test-data --galaxy_root /home/biodocker/galaxy-central {ptestpath}"
        try:
            rlog = container.exec_run(ptestcl)
            # fails because test outputs missing but updates the test-data directory
        except:
            e = sys.exc_info()[0]
            tout.write(f"#### error: {e} from {ptestcl}\n")
        cl = f"planemo test  --test_output {imrep} --no_cleanup --test_data {destdir}/tfout/test-data --galaxy_root /home/biodocker/galaxy-central {ptestpath}"
        try:
            prun(container, tout, cl)
        except:
            e = sys.exc_info()[0]
            tout.write(f"#### error: {e} from {ptestcl}\n")
        testouts = tempfile.mkdtemp(suffix=None, prefix="tftemp", dir=".")
        self.copy_from_container(destdir, testouts, container)
        src = os.path.join(testouts, "ptest")
        if os.path.isdir(src):
            shutil.copytree(src, ".", dirs_exist_ok=True)
            src = repname
            if os.path.isfile(repname):
                shutil.copyfile(src, ptestrep_path)
        else:
            tout.write(f"No output from run to shutil.copytree in {src}\n")
        tout.close()
        container.stop()
        container.remove()
        tvol.remove()
        shutil.rmtree(testouts) # leave for debugging

    def planemo_test(self, genoutputs=True):
            """planemo is a requirement so is available for testing but needs a different call if
            in the biocontainer - see above
            and for generating test outputs if command or test overrides are supplied
            test outputs are sent to repdir for display
            planemo test --engine docker_galaxy  --galaxy_root /galaxy-central pyrevpos/pyrevpos.xml
            Planemo runs:
    python ./scripts/functional_tests.py -v --with-nosehtml --html-report-file
    /export/galaxy-central/database/job_working_directory/000/17/working/TF_run_report_tempdir/tacrev_planemo_test_report.html
    --with-xunit --xunit-file /tmp/tmpt90p7f9h/xunit.xml --with-structureddata
    --structured-data-file
    /export/galaxy-central/database/job_working_directory/000/17/working/tfout/tool_test_output.json functional.test_toolbox
            for the planemo-biocontainer,
            planemo test --conda_dependency_resolution --skip_venv --galaxy_root /galthrow/ rgToolFactory2.xml
            """
            xreal = "%s.xml" % self.tool_name
            tool_test_path = os.path.join(self.repdir,f"{self.tool_name}_planemo_test_report.html")
            if os.path.exists(self.tlog):
                tout = open(self.tlog, "a")
            else:
                tout = open(self.tlog, "w")
            if genoutputs:
                dummy, tfile = tempfile.mkstemp()
                cll = [
                    "planemo",
                    "test",
                    "--test_data", os.path.abspath(self.testdir),
                    "--test_output", os.path.abspath(tool_test_path),
                    "--skip_venv",
                    "--galaxy_root",
                    self.args.galaxy_root,
                    "--update_test_data",
                    os.path.abspath(xreal),
                ]
                p = subprocess.run(
                    cll,
                    shell=False,
                    cwd=self.tooloutdir,
                    stderr=dummy,
                    stdout=dummy,
                )

            else:
                cll = [
                    "planemo",
                    "test",
                    "--test_data", os.path.abspath(self.testdir),
                    "--test_output", os.path.abspath(tool_test_path),
                    "--skip_venv",
                    "--galaxy_root",
                    self.args.galaxy_root,
                    os.path.abspath(xreal),
                ]
                p = subprocess.run(
                    cll, shell=False, cwd=self.tooloutdir, stderr=tout, stdout=tout
                )
            tout.close()
            return p.returncode



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
            url=self.args.toolshed_url, key=self.args.toolshed_api_key, verify=False
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
            cll, env=self.ourenv, cwd=self.ourcwd, shell=False, stderr=tout, stdout=tout
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
        self.makeXML()
        if self.args.script_path:
            stname = os.path.join(self.tooloutdir, "%s" % (self.sfile))
            if not os.path.exists(stname):
                shutil.copyfile(self.sfile, stname)
        xreal = "%s.xml" % self.tool_name
        xout = os.path.join(self.tooloutdir, xreal)
        shutil.copyfile(xreal, xout)
        for p in self.infiles:
            pth = p[IPATHPOS]
            dest = os.path.join(self.testdir, "%s_sample" % p[ICLPOS])
            shutil.copyfile(pth, dest)

    def makeToolTar(self):
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
            oname = p[ONAMEPOS]
            tdest = os.path.join(self.testdir, "%s_sample" % oname)
            if not os.path.isfile(tdest):
                src = os.path.join(self.testdir, oname)
                if os.path.isfile(src):
                    shutil.copyfile(src, tdest)
                    dest = os.path.join(self.repdir, "%s.sample" % (oname))
                    shutil.copyfile(src, dest)
                else:
                    tout.write(
                        "###Output file %s not found in testdir %s. This is normal during the first Planemo run that generates test outputs"
                        % (tdest, self.testdir)
                    )
        tf = tarfile.open(self.newtarpath, "w:gz")
        tf.add(name=self.tooloutdir, arcname=self.tool_name, filter=exclude_function)
        tf.close()
        shutil.copyfile(self.newtarpath, self.args.new_tool)

    def moveRunOutputs(self):
        """need to move planemo or run outputs into toolfactory collection"""
        with os.scandir(self.tooloutdir) as outs:
            for entry in outs:
                if not entry.is_file():
                    continue
                if "." in entry.name:
                    nayme, ext = os.path.splitext(entry.name)
                    if ext in [".yml", ".xml", ".json", ".yaml"]:
                        ext = f"{ext}.txt"
                else:
                    ext = ".txt"
                ofn = "%s%s" % (entry.name.replace(".", "_"), ext)
                dest = os.path.join(self.repdir, ofn)
                src = os.path.join(self.tooloutdir, entry.name)
                shutil.copyfile(src, dest)
        with os.scandir(self.testdir) as outs:
            for entry in outs:
                if (
                    (not entry.is_file())
                    or entry.name.endswith("_sample")
                    or entry.name.endswith("_planemo_test_report.html")
                ):
                    continue
                if "." in entry.name:
                    nayme, ext = os.path.splitext(entry.name)
                else:
                    ext = ".txt"
                newname = f"{entry.name}{ext}"
                dest = os.path.join(self.repdir, newname)
                src = os.path.join(self.testdir, entry.name)
                shutil.copyfile(src, dest)


def main():
    """
    This is a Galaxy wrapper. It expects to be called by a special purpose tool.xml

    """
    parser = argparse.ArgumentParser()
    a = parser.add_argument
    a("--script_path", default=None)
    a("--history_test", default=None)
    a("--cl_prefix", default=None)
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
    a("--edit_additional_parameters", action="store_true", default=False)
    a("--parampass", default="positional")
    a("--tfout", default="./tfout")
    a("--new_tool", default="new_tool")
    a("--galaxy_url", default="http://localhost:8080")
    a("--toolshed_url", default="http://localhost:9009")
    # make sure this is identical to tool_sheds_conf.xml  localhost != 127.0.0.1 so validation fails
    a("--toolshed_api_key", default="fakekey")
    a("--galaxy_api_key", default="fakekey")
    a("--galaxy_root", default="/galaxy-central")
    a("--galaxy_venv", default="/galaxy_venv")
    args = parser.parse_args()
    assert not args.bad_user, (
        'UNAUTHORISED: %s is NOT authorized to use this tool until Galaxy admin adds %s to "admin_users" in the galaxy.yml Galaxy configuration file'
        % (args.bad_user, args.bad_user)
    )
    assert args.tool_name, "## Tool Factory expects a tool name - eg --tool_name=DESeq"
    assert (
        args.sysexe or args.packages
    ), "## Tool Factory wrapper expects an interpreter or an executable package"
    args.input_files = [x.replace('"', "").replace("'", "") for x in args.input_files]
    # remove quotes we need to deal with spaces in CL params
    for i, x in enumerate(args.additional_parameters):
        args.additional_parameters[i] = args.additional_parameters[i].replace('"', "")
    r = ScriptRunner(args)
    r.writeShedyml()
    r.makeTool()
    if args.make_Tool == "generate":
        retcode = r.run()
        r.moveRunOutputs()
        r.makeToolTar()
    else:
        retcode = r.planemo_test(genoutputs=True)  # this fails :( - see PR
        r.moveRunOutputs()
        r.makeToolTar()
        retcode = r.planemo_test(genoutputs=False)
        r.moveRunOutputs()
        r.makeToolTar()
        print(f"second planemo_test returned {retcode}")
        if args.make_Tool == "gentestinstall":
            r.shedLoad()
            r.eph_galaxy_load()
    # for the docker version use this
    # if args.make_Tool == "generate":
        # retcode = r.run()  # for testing toolfactory itself
        # r.moveRunOutputs()
        # r.makeToolTar()
    # else:
        # r.planemo_biodocker_test()  # test to make outputs and then test
        # r.moveRunOutputs()
        # r.makeToolTar()
        # if args.make_Tool == "gentestinstall":
            # r.shedLoad()
            # r.eph_galaxy_load()


if __name__ == "__main__":
    main()
