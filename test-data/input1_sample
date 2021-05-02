#!/usr/bin/env python
# rgToolFactory.py
# see https://github.com/fubar2/toolfactory
#
# copyright ross lazarus (ross stop lazarus at gmail stop com) May 2012
#
# all rights reserved
# Licensed under the LGPL
# suggestions for improvement and bug fixes welcome at https://github.com/fubar2/toolfactory
#
# July 2020: BCC was fun and I feel like rip van winkle after 5 years.
# Decided to
# 1. Fix the toolfactory so it works - done for simplest case
# 2. Fix planemo so the toolfactory function works
# 3. Rewrite bits using galaxyxml functions where that makes sense - done
#
# removed all the old complications including making the new tool use this same script
# galaxyxml now generates the tool xml https://github.com/hexylena/galaxyxml
# No support for automatic HTML file creation from arbitrary outputs
# TODO: add option to run that code as a post execution hook
# TODO: add additional history input parameters - currently only one


import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

import galaxyxml.tool as gxt
import galaxyxml.tool.parameters as gxtp

import lxml

myversion = "V2.1 July 2020"
verbose = True
debug = True
toolFactoryURL = "https://github.com/fubar2/toolfactory"
ourdelim = "~~~"

# --input_files="$input_files~~~$CL~~~$input_formats~~~$input_label
# ~~~$input_help"
IPATHPOS = 0
ICLPOS = 1
IFMTPOS = 2
ILABPOS = 3
IHELPOS = 4
IOCLPOS = 5

# --output_files "$otab.history_name~~~$otab.history_format~~~$otab.CL
ONAMEPOS = 0
OFMTPOS = 1
OCLPOS = 2
OOCLPOS = 3

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

def timenow():
    """return current time as a string
    """
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


html_escape_table = {"&": "&amp;", ">": "&gt;", "<": "&lt;", "$": r"\$"}


def html_escape(text):
    """Produce entities within text."""
    return "".join(html_escape_table.get(c, c) for c in text)


def html_unescape(text):
    """Revert entities within text. Multiple character targets so use replace"""
    t = text.replace("&amp;", "&")
    t = t.replace("&gt;", ">")
    t = t.replace("&lt;", "<")
    t = t.replace("\\$", "$")
    return t


def parse_citations(citations_text):
    """
    """
    citations = [c for c in citations_text.split("**ENTRY**") if c.strip()]
    citation_tuples = []
    for citation in citations:
        if citation.startswith("doi"):
            citation_tuples.append(("doi", citation[len("doi") :].strip()))
        else:
            citation_tuples.append(
                ("bibtex", citation[len("bibtex") :].strip())
            )
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
        aCL = self.cl.append
        assert args.parampass in [
            "0",
            "argparse",
            "positional",
        ], 'Parameter passing in args.parampass must be "0","positional" or "argparse"'
        self.tool_name = re.sub("[^a-zA-Z0-9_]+", "", args.tool_name)
        self.tool_id = self.tool_name
        if self.args.interpreter_name:
            exe = "$runMe"
        else:
            exe = self.args.exe_package
        assert (
            exe is not None
        ), "No interpeter or executable passed in - nothing to run so cannot build"
        self.tool = gxt.Tool(
            self.args.tool_name,
            self.tool_id,
            self.args.tool_version,
            self.args.tool_desc,
            exe,
        )
        self.tinputs = gxtp.Inputs()
        self.toutputs = gxtp.Outputs()
        self.testparam = []
        if (
            self.args.runmode == "Executable" or self.args.runmode == "system"
        ):  # binary - no need
            aCL(self.args.exe_package)  # this little CL will just run
        else:
            self.prepScript()
        self.elog = "%s_error_log.txt" % self.tool_name
        self.tlog = "%s_runner_log.txt" % self.tool_name

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
                # print('##infile i=%d, appendme=%s' % (i,appendme))
            for i, p in enumerate(self.outfiles):
                if p[OOCLPOS] == "STDOUT":
                    self.lastclredirect = [">", p[ONAMEPOS]]
                    self.lastxclredirect = [">", "$%s" % p[OCLPOS]]
                else:
                    clsuffix.append([p[OOCLPOS], p[OCLPOS], p[ONAMEPOS], ""])
                    xclsuffix.append(
                        [p[OOCLPOS], p[OCLPOS], "$%s" % p[ONAMEPOS], ""]
                    )
            for p in self.addpar:
                clsuffix.append(
                    [p[AOCLPOS], p[ACLPOS], p[AVALPOS], p[AOVERPOS]]
                )
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
        aCL = self.cl.append
        rx = open(self.args.script_path, "r").readlines()
        rx = [x.rstrip() for x in rx]
        rxcheck = [x.strip() for x in rx if x.strip() > ""]
        assert len(rxcheck) > 0, "Supplied script is empty. Cannot run"
        self.script = "\n".join(rx)
        fhandle, self.sfile = tempfile.mkstemp(
            prefix=self.tool_name, suffix="_%s" % (self.args.interpreter_name)
        )
        tscript = open(self.sfile, "w")
        tscript.write(self.script)
        tscript.close()
        self.indentedScript = "  %s" % "\n".join(
            [" %s" % html_escape(x) for x in rx]
        )
        self.escapedScript = "%s" % "\n".join(
            [" %s" % html_escape(x) for x in rx]
        )
        art = "%s.%s" % (self.tool_name, self.args.interpreter_name)
        artifact = open(art, "wb")
        artifact.write(bytes(self.script, "utf8"))
        artifact.close()
        aCL(self.args.interpreter_name)
        aCL(self.sfile)

    def cleanuppar(self):
        """ positional parameters are complicated by their numeric ordinal"""
        for i, p in enumerate(self.infiles):
            if self.args.parampass == "positional":
                assert p[ICLPOS].isdigit(), (
                    "Positional parameters must be ordinal integers - got %s for %s"
                    % (p[ICLPOS], p[ILABPOS])
                )
            p.append(p[ICLPOS])
            if p[ICLPOS].isdigit() or self.args.parampass == "0":
                scl = "input%d" % (i + 1)
                p[ICLPOS] = scl
            self.infiles[i] = p
        for i, p in enumerate(
            self.outfiles
        ):  # trying to automagically gather using extensions
            if self.args.parampass == "positional" and p[OCLPOS] != "STDOUT":
                assert p[OCLPOS].isdigit(), (
                    "Positional parameters must be ordinal integers - got %s for %s"
                    % (p[OCLPOS], p[ONAMEPOS])
                )
            p.append(p[OCLPOS])
            if p[OCLPOS].isdigit() or p[OCLPOS] == "STDOUT":
                scl = p[ONAMEPOS]
                p[OCLPOS] = scl
            self.outfiles[i] = p
        for i, p in enumerate(self.addpar):
            if self.args.parampass == "positional":
                assert p[ACLPOS].isdigit(), (
                    "Positional parameters must be ordinal integers - got %s for %s"
                    % (p[ACLPOS], p[ANAMEPOS])
                )
            p.append(p[ACLPOS])
            if p[ACLPOS].isdigit():
                scl = "input%s" % p[ACLPOS]
                p[ACLPOS] = scl
            self.addpar[i] = p

    def clsimple(self):
        """ no parameters - uses < and > for i/o
        """
        aCL = self.cl.append
        aCL("<")
        aCL(self.infiles[0][IPATHPOS])
        aCL(">")
        aCL(self.outfiles[0][OCLPOS])
        aXCL = self.xmlcl.append
        aXCL("<")
        aXCL("$%s" % self.infiles[0][ICLPOS])
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
        """ argparse style
        """
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
        for p in self.outfiles:
            newname, newfmt, newcl, oldcl = p
            ndash = self.getNdash(newcl)
            aparm = gxtp.OutputData(newcl, format=newfmt, num_dashes=ndash)
            aparm.positional = self.is_positional
            if self.is_positional:
                if oldcl == "STDOUT":
                    aparm.positional = 9999999
                    aparm.command_line_override = "> $%s" % newcl
                else:
                    aparm.positional = int(oldcl)
                    aparm.command_line_override = "$%s" % newcl
            self.toutputs.append(aparm)
            tp = gxtp.TestOutput(
                name=newcl, value="%s_sample" % newcl, format=newfmt
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
                aninput.positional = int(oldcl)
            self.tinputs.append(aparm)
            self.tparm = gxtp.TestParam(newname, value=newval)
            self.testparam.append(tparm)

    def doNoXMLparam(self):
        alab = self.infiles[0][ILABPOS]
        if len(alab) == 0:
            alab = self.infiles[0][ICLPOS]
        max1s = (
            "Maximum one input if parampass is 0 - more than one input files supplied - %s"
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
        self.tool.command_line_override = self.xmlcl
        if self.args.interpreter_name:
            self.tool.interpreter = self.args.interpreter_name
        if self.args.help_text:
            helptext = open(self.args.help_text, "r").readlines()
            helptext = [html_escape(x) for x in helptext]
            self.tool.help = "".join([x for x in helptext])
        else:
            self.tool.help = (
                "Please ask the tool author (%s) for help \
              as none was supplied at tool generation\n"
                % (self.args.user_email)
            )
        self.tool.version_command = None  # do not want
        requirements = gxtp.Requirements()

        if self.args.interpreter_name:
            if self.args.interpreter_name == "python":
                requirements.append(
                    gxtp.Requirement(
                        "package", "python", self.args.interpreter_version
                    )
                )
            elif self.args.interpreter_name not in ["bash", "sh"]:
                requirements.append(
                    gxtp.Requirement(
                        "package",
                        self.args.interpreter_name,
                        self.args.interpreter_version,
                    )
                )
        else:
            if self.args.exe_package and self.args.parampass != "system":
                requirements.append(
                    gxtp.Requirement(
                        "package",
                        self.args.exe_package,
                        self.args.exe_package_version,
                    )
                )
        self.tool.requirements = requirements
        if self.args.parampass == "0":
            self.doNoXMLparam()
        else:
            self.doXMLparam()
        self.tool.outputs = self.toutputs
        self.tool.inputs = self.tinputs
        if self.args.runmode not in ["Executable", "system"]:
            configfiles = gxtp.Configfiles()
            configfiles.append(gxtp.Configfile(name="runMe", text=self.script))
            self.tool.configfiles = configfiles
        tests = gxtp.Tests()
        test_a = gxtp.Test()
        for tp in self.testparam:
            test_a.append(tp)
        tests.append(test_a)
        self.tool.tests = tests
        self.tool.add_comment(
            "Created by %s at %s using the Galaxy Tool Factory."
            % (self.args.user_email, timenow())
        )
        self.tool.add_comment("Source in git at: %s" % (toolFactoryURL))
        self.tool.add_comment(
            "Cite: Creating re-usable tools from scripts doi: 10.1093/bioinformatics/bts573"
        )
        exml = self.tool.export()
        xf = open('%s.xml' % self.tool_name, "w")
        xf.write(exml)
        xf.write("\n")
        xf.close()
        # ready for the tarball

    def makeTooltar(self):
        """
        a tool is a gz tarball with eg
        /toolname/tool.xml /toolname/tool.py /toolname/test-data/test1_in.foo ...
        NOTE names for test inputs and outputs are munged here so must
        correspond to actual input and output names used on the generated cl
        """
        retval = self.run()
        if retval:
            sys.stderr.write(
                "## Run failed. Cannot build yet. Please fix and retry"
            )
            sys.exit(1)
        tdir = "tfout"
        if not os.path.exists(tdir):
            os.mkdir(tdir)
        self.makeXML()
        testdir = os.path.join(tdir, "test-data")
        if not os.path.exists(testdir):
            os.mkdir(testdir)  # make tests directory
        for p in self.infiles:
            pth = p[IPATHPOS]
            dest = os.path.join(testdir, "%s_sample" % p[ICLPOS])
            shutil.copyfile(pth, dest)
        for p in self.outfiles:
            pth = p[OCLPOS]
            if p[OOCLPOS] == "STDOUT" or self.args.parampass == "0":
                pth = p[ONAMEPOS]
                dest = os.path.join(testdir, "%s_sample" % p[ONAMEPOS])
                shutil.copyfile(pth, dest)
                dest = os.path.join(tdir, p[ONAMEPOS])
                shutil.copyfile(pth, dest)
            else:
                pth = p[OCLPOS]
                dest = os.path.join(testdir, "%s_sample" % p[OCLPOS])
                shutil.copyfile(pth, dest)
                dest = os.path.join(tdir, p[OCLPOS])
                shutil.copyfile(pth, dest)

        if os.path.exists(self.tlog) and os.stat(self.tlog).st_size > 0:
            shutil.copyfile(self.tlog, os.path.join(testdir, "test1_log_outfiletxt"))
        if self.args.runmode not in ["Executable", "system"]:
            stname = os.path.join(tdir, "%s" % (self.sfile))
            if not os.path.exists(stname):
                shutil.copyfile(self.sfile, stname)
        xreal = '%s.xml' % self.tool_name
        xout = os.path.join(tdir,xreal)
        shutil.copyfile(xreal, xout)
        tarpath = "toolfactory_%s.tgz" % self.tool_name
        tf = tarfile.open(tarpath, "w:gz")
        tf.add(name=tdir, arcname=self.tool_name)
        tf.close()
        shutil.copyfile(tarpath, self.args.new_tool)
        shutil.copyfile(xreal,"tool_xml.txt")
        repdir = "TF_run_report_tempdir"
        if not os.path.exists(repdir):
            os.mkdir(repdir)
        repoutnames = [x[OCLPOS] for x in self.outfiles]
        with os.scandir('.') as outs:
            for entry in outs:
                if entry.name.endswith('.tgz') or not entry.is_file():
                    continue
                if entry.name in repoutnames:
                    shutil.copyfile(entry.name,os.path.join(repdir,entry.name))
                elif entry.name == "%s.xml" % self.tool_name:
                    shutil.copyfile(entry.name,os.path.join(repdir,"new_tool_xml"))
        return retval

    def run(self):
        """
        Some devteam tools have this defensive stderr read so I'm keeping with the faith
        Feel free to update.
        """
        s = "run cl=%s" % str(self.cl)

        logging.debug(s)
        scl = " ".join(self.cl)
        err = None
        if self.args.parampass != "0":
            ste = open(self.elog, "wb")
            if self.lastclredirect:
                sto = open(
                    self.lastclredirect[1], "wb"
                )  # is name of an output file
            else:
                sto = open(self.tlog, "wb")
                sto.write(
                    bytes(
                        "## Executing Toolfactory generated command line = %s\n"
                        % scl,
                        "utf8",
                    )
                )
            sto.flush()
            p = subprocess.run(self.cl, shell=False, stdout=sto, stderr=ste)
            sto.close()
            ste.close()
            tmp_stderr = open(self.elog, "rb")
            err = ""
            buffsize = 1048576
            try:
                while True:
                    err += str(tmp_stderr.read(buffsize))
                    if not err or len(err) % buffsize != 0:
                        break
            except OverflowError:
                pass
            tmp_stderr.close()
            retval = p.returncode
        else:  # work around special case of simple scripts that take stdin and write to stdout
            sti = open(self.infiles[0][IPATHPOS], "rb")
            sto = open(self.outfiles[0][ONAMEPOS], "wb")
            # must use shell to redirect
            p = subprocess.run(self.cl, shell=False, stdout=sto, stdin=sti)
            retval = p.returncode
            sto.close()
            sti.close()
        if os.path.isfile(self.tlog) and os.stat(self.tlog).st_size == 0:
            os.unlink(self.tlog)
        if os.path.isfile(self.elog) and os.stat(self.elog).st_size == 0:
            os.unlink(self.elog)
        if p.returncode != 0 and err:  # problem
            sys.stderr.write(err)
        logging.debug("run done")
        return retval


def main():
    """
    This is a Galaxy wrapper. It expects to be called by a special purpose tool.xml as:
    <command interpreter="python">rgBaseScriptWrapper.py --script_path "$scriptPath" --tool_name "foo" --interpreter "Rscript"
    </command>
    """
    parser = argparse.ArgumentParser()
    a = parser.add_argument
    a("--script_path", default="")
    a("--tool_name", default=None)
    a("--interpreter_name", default=None)
    a("--interpreter_version", default=None)
    a("--exe_package", default=None)
    a("--exe_package_version", default=None)
    a("--input_files", default=[], action="append")
    a("--output_files", default=[], action="append")
    a("--user_email", default="Unknown")
    a("--bad_user", default=None)
    a("--make_Tool", default=None)
    a("--help_text", default=None)
    a("--tool_desc", default=None)
    a("--tool_version", default=None)
    a("--citations", default=None)
    a("--additional_parameters", action="append", default=[])
    a("--edit_additional_parameters", action="store_true", default=False)
    a("--parampass", default="positional")
    a("--tfout", default="./tfout")
    a("--new_tool", default="new_tool")
    a("--runmode", default=None)
    args = parser.parse_args()
    assert not args.bad_user, (
        'UNAUTHORISED: %s is NOT authorized to use this tool until Galaxy admin adds %s to "admin_users" in the Galaxy configuration file'
        % (args.bad_user, args.bad_user)
    )
    assert (
        args.tool_name
    ), "## Tool Factory expects a tool name - eg --tool_name=DESeq"
    assert (
        args.interpreter_name or args.exe_package
    ), "## Tool Factory wrapper expects an interpreter or an executable package"
    assert args.exe_package or (
        len(args.script_path) > 0 and os.path.isfile(args.script_path)
    ), "## Tool Factory wrapper expects a script path - eg --script_path=foo.R if no executable"
    args.input_files = [
        x.replace('"', "").replace("'", "") for x in args.input_files
    ]
    # remove quotes we need to deal with spaces in CL params
    for i, x in enumerate(args.additional_parameters):
        args.additional_parameters[i] = args.additional_parameters[i].replace(
            '"', ""
        )
    r = ScriptRunner(args)
    if args.make_Tool:
        retcode = r.makeTooltar()
    else:
        retcode = r.run()
    if retcode:
        sys.exit(retcode)  # indicate failure to job runner


if __name__ == "__main__":
    main()
