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

import sys
import subprocess
import shutil
import os
import time
import tempfile
import argparse
import tarfile
import re
import galaxyxml.tool as gxt
import galaxyxml.tool.parameters as gxtp
import logging


progname = os.path.split(sys.argv[0])[1]
myversion = 'V2.1 July 2020'
verbose = True
debug = True
toolFactoryURL = 'https://github.com/fubar2/toolfactory'
ourdelim = '~~~'

# --input_files="$input_files~~~$CL~~~$input_formats~~~$input_label~~~$input_help"
IPATHPOS = 0
ICLPOS = 1
IFMTPOS = 2
ILABPOS = 3
IHELPOS = 4

# --output_files "$otab.history_name~~~$otab.history_format~~~$otab.CL
ONAMEPOS = 0
OFMTPOS = 1
OCLPOS = 2


#--additional_parameters="$i.param_name~~~$i.param_value~~~$i.param_label~~~$i.param_help~~~$i.param_type~~~$i.CL"
ANAMEPOS = 0
AVALPOS = 1
ALABPOS = 1
AHELPPOS = 1
ATYPEPOS = 1
ACLPOS = 1

def timenow():
    """return current time as a string
    """
    return time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(time.time()))


def quote_non_numeric(s):
    """return a prequoted string for non-numerics
    useful for perl and Rscript parameter passing?
    """
    try:
        _ = float(s)
        return s
    except ValueError:
        return '"%s"' % s


html_escape_table = {
    "&": "&amp;",
    ">": "&gt;",
    "<": "&lt;",
    "$": r"\$"
}


def html_escape(text):
    """Produce entities within text."""
    return "".join(html_escape_table.get(c, c) for c in text)


def html_unescape(text):
    """Revert entities within text. Multiple character targets so use replace"""
    t = text.replace('&amp;', '&')
    t = t.replace('&gt;', '>')
    t = t.replace('&lt;', '<')
    t = t.replace('\\$', '$')
    return t


def parse_citations(citations_text):
    """
    """
    citations = [c for c in citations_text.split("**ENTRY**") if c.strip()]
    citation_tuples = []
    for citation in citations:
        if citation.startswith("doi"):
            citation_tuples.append(("doi", citation[len("doi"):].strip()))
        else:
            citation_tuples.append(
                ("bibtex", citation[len("bibtex"):].strip()))
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
        self.cleanuppar()
        self.lastclredirect = None
        self.cl = []
        aCL = self.cl.append
        self.args = args
        assert args.parampass in ['0','argparse','positional'],'Parameter passing in args.parampass must be "0","positional" or "argparse"'
        self.tool_name = re.sub('[^a-zA-Z0-9_]+', '', args.tool_name)
        self.tool_id = self.tool_name
        self.xmlfile = '%s.xml' % self.tool_name
        if self.args.interpreter_name == "Executable":  # binary - no need
            aCL(self.args.exe_package)  # this little CL will just run
        else:  # a script has been provided
            rx = open(self.args.script_path, 'r').readlines()
            # remove pesky dos line endings if needed
            rx = [x.rstrip() for x in rx]
            self.script = '\n'.join(rx)
            fhandle, self.sfile = tempfile.mkstemp(
                prefix=self.tool_name, suffix=".%s" % (args.interpreter_name))
            # use self.sfile as script source for Popen
            tscript = open(self.sfile, 'w')
            tscript.write(self.script)
            tscript.close()
            self.indentedScript = "  %s" % '\n'.join(
                [' %s' % html_escape(x) for x in rx])  # for restructured text in help
            self.escapedScript = "%s" % '\n'.join(
                [' %s' % html_escape(x) for x in rx])
            aCL(self.args.interpreter_name)
            aCL(self.sfile)
        self.elog = "%s_error_log.txt" % self.tool_name
        self.tlog = "%s_runner_log.txt" % self.tool_name
        art = '%s.%s' % (self.tool_name, args.interpreter_name)
        # use self.sfile as script source for Popen
        artifact = open(art, 'wb')
        artifact.write(bytes(self.script, "utf8"))
        artifact.close()
        if self.args.parampass == '0':
            self.clsimple()
        else:
            clsuffix = []
            for i, p in enumerate(self.infiles):
                # decorator is cl - sort for positional
                clsuffix.append([p[ICLPOS], p[IPATHPOS]])
            for i, p in enumerate(self.outfiles):
                # decorator is cl - sort for positional
                clsuffix.append([p[OCLPOS], p[OCLPOS]])            
            for p in self.args.additional_parameters: 
                clsuffix.append([p[ACLPOS], p[AVALPOS]])  # cl,value
            clsuffix.sort()
            if self.args.parampass == 'positional':
                self.clpositional(clsuffix)
            else:
                self.clargparse(clsuffix)
                
    def cleanuppar(self):
        """ positional parameters are complicated by their numeric ordinal"""
        for i,p in enumerate(self.infiles):
            if p[ICLPOS].isdigit() or p[ICLPOS].strip().upper() in ['STDOUT', 'STDIN']:
                scl = 'input%s' % p[ICLPOS]
                self.infiles[i][ICLPOS] = scl
        for i,p in enumerate(self.outfiles):  # trying to automagically gather using extensions
            if p[OCLPOS].isdigit() or p[OCLPOS].strip().upper() in ['STDOUT', 'STDIN']:
                scl = 'output%s.%s' % (p[OCLPOS],p[OFMTPOS])
                self.outfiles[i][OCLPOS] = scl
            if not p[ONAMEPOS].endswith(p[OFMTPOS]):
                self.outfiles[i][ONAMEPOS] = '%s_%s' % (p[ONAMEPOS],p[OFMTPOS])
        for i,p in enumerate(self.addpar):
            if p[ACLPOS].isdigit() or p[ACLPOS].strip().upper() in ['STDOUT', 'STDIN']:
                scl = 'param%s' % p[ACLPOS]
                self.addpar[i][ACLPOS] = scl
                
 
            
    def clsimple(self):
        """ no parameters - uses < and > for i/o
        """
        aCL = self.cl.append
        aCL('<')
        aCL('%s' % self.infiles[0][IPATHPOS])
        aCL('>')
        ocl = self.outfiles[0][OCLPOS] # galaxy name
        aCL(ocl)

    def clpositional(self,clsuffix):
        # inputs in order then params
        aCL = self.cl.append
        for (k, v) in clsuffix:
            if ' ' in v:
                aCL("%s" % v)
            else:
                aCL(v)
        if self.lastclredirect:
            aCL(self.lastclredirect[0])  # add the stdout parameter last
            aCL(self.lastclredirect[1])

    def clargparse(self,clsuffix):
        """ no parameters - uses < and > for i/o
        """
        aCL = self.cl.append
        # inputs then params in argparse named form
        for (k, v) in clsuffix:
            if ' ' in v:
                aCL('--%s' % k)
                aCL('"%s"' % v)
            else:
                aCL('--%s' % k)
                aCL('%s' % v)
        if self.lastclredirect:
            aCL(self.lastclredirect[0])  # add the stdout parameter last
            aCL(self.lastclredirect[1])


    def makeXML(self):
        """
        Create a Galaxy xml tool wrapper for the new script
        Uses galaxyhtml
        """
        # need interp and executable (?script) or else executable only
        if self.args.interpreter_name:
            exe = "$runMe"  # our dynamic script from the tool builder
            interp = self.args.interpreter_name
        else:
            interp = None
            exe = self.args.exe_package
        assert exe is not None, 'No interpeter or executable passed in to makeXML'
        tool = gxt.Tool(self.args.tool_name, self.tool_id,
                        self.args.tool_version, self.args.tool_desc, exe)
        if interp:
            tool.interpreter = interp
        if self.args.help_text:
            helptext = open(self.args.help_text, 'r').readlines()
            # must html escape here too - thanks to Marius van den Beek
            helptext = [html_escape(x) for x in helptext]
            tool.help = ''.join([x for x in helptext])
        else:
            tool.help = 'Please ask the tool author (%s) for help \
              as none was supplied at tool generation\n' % (self.args.user_email)
        tool.version_command = None  # do not want
        tinputs = gxtp.Inputs()
        toutputs = gxtp.Outputs()
        requirements = gxtp.Requirements()
        testparam = []
        is_positional = (self.args.parampass == 'positional')
        if self.args.interpreter_name:
            if self.args.interpreter_name == 'python':  # always needed for this runner script
                requirements.append(gxtp.Requirement(
                    'package', 'python', self.args.interpreter_version))
            elif self.args.interpreter_name not in ['bash', 'sh']:
                requirements.append(gxtp.Requirement(
                    'package', self.args.interpreter_name, self.args.interpreter_version))
        else:
            if self.args.exe_package:  # uses exe not interpreter
                requirements.append(gxtp.Requirement(
                    'package', self.args.exe_package, self.args.exe_package_version))
        tool.requirements = requirements
        if self.args.parampass == '0': # foo < input1.txt > output1.txt
            alab = self.infiles[0][ILABPOS]
            if len(alab) == 0:
                alab = self.infiles[0][ICLPOS]
            max1s = 'Maximum one input if parampass is 0 - more than one input files supplied - %s' % str(self.infiles)
            assert len(self.infiles) == 1,max1s
            newname = self.infiles[0][ICLPOS]
            aninput = gxtp.DataParam(newname, optional=False, label=alab, help=self.infiles[0][IHELPOS],
                                    format=self.infiles[0][IFMTPOS], multiple=False, num_dashes=0)
            aninput.command_line_override = '< $%s' % newname
            tinputs.append(aninput)
            tp = gxtp.TestParam(name=newname, value='%s.sample' % newname)
            testparam.append(tp)
            newname = self.outfiles[0][OCLPOS]
            newfmt = self.outfiles[0][OFMTPOS]
            anout = gxtp.OutputData(newname, format=newfmt, num_dashes=0)
            anout.command_line_override = '> $%s' % newname
            anout.positional = is_positional
            toutputs.append(anout)
            tp = gxtp.TestOutput(name=newname, value='%s.sample' % newname,format=newfmt)
            testparam.append(tp)
        else:
            for p in self.outfiles:
                newname,newfmt,newcl = p
                if is_positional:
                    ndash = 0
                else:
                    ndash = 2
                    if len(newcl) < 2:
                        ndash = 1
                aparm = gxtp.OutputData(newcl, format=newfmt, num_dashes=ndash)
                aparm.positional = is_positional
                if is_positional:
                    aparm.command_line_override = '$%s' % newcl
                toutputs.append(aparm)
                tp = gxtp.TestOutput(name=newcl, value='%s.sample' % newcl ,format=newfmt)
                testparam.append(tp)
            for p in self.infiles:
                newname = p[ICLPOS]
                newfmt = p[IFMTPOS]
                if is_positional:
                    ndash = 0
                else:
                    if len(newname) > 1:
                        ndash = 2
                    else:
                        ndash = 1
                if not len(p[ILABPOS]) > 0:
                    alab = p[ICLPOS]
                else:
                    alab = p[ILABPOS]
                aninput = gxtp.DataParam(newname, optional=False, label=alab, help=p[IHELPOS],
                                         format=newfmt, multiple=False, num_dashes=ndash)
                aninput.positional = is_positional
                tinputs.append(aninput)
                tparm = gxtp.TestParam(name=newname, value='%s.sample' % newname )
                testparam.append(tparm)
            for p in self.addpar:
                newname, newval, newlabel, newhelp, newtype, newcl = p
                if not len(newlabel) > 0:
                    newlabel = newname
                if is_positional:
                    ndash = 0
                else:
                    if len(newname) > 1:
                        ndash = 2
                    else:
                        ndash = 1
                if newtype == "text":
                    aparm = gxtp.TextParam(
                        newname, label=newlabel, help=newhelp, value=newval, num_dashes=ndash)
                elif newtype == "integer":
                    aparm = gxtp.IntegerParam(
                        newname, label=newname, help=newhelp, value=newval, num_dashes=ndash)
                elif newtype == "float":
                    aparm = gxtp.FloatParam(
                        newname, label=newname, help=newhelp, value=newval, num_dashes=ndash)
                else:
                    raise ValueError('Unrecognised parameter type "%s" for\
                     additional parameter %s in makeXML' % (newtype, newname))
                aparm.positional = is_positional
                tinputs.append(aparm)
                tparm = gxtp.TestParam(newname, value=newval)
                testparam.append(tparm)
        tool.outputs = toutputs
        tool.inputs = tinputs
        configfiles = gxtp.Configfiles()
        configfiles.append(gxtp.Configfile(name="runMe", text=self.script))
        tool.configfiles = configfiles
        tests = gxtp.Tests()
        test_a = gxtp.Test()
        for tp in testparam:
            test_a.append(tp)
        tests.append(test_a)
        tool.tests = tests
        tool.add_comment('Created by %s at %s using the Galaxy Tool Factory.' % (
            self.args.user_email, timenow()))
        tool.add_comment('Source in git at: %s' % (toolFactoryURL))
        tool.add_comment(
            'Cite: Creating re-usable tools from scripts doi: 10.1093/bioinformatics/bts573')
        exml = tool.export()
        xf = open(self.xmlfile, 'w')
        xf.write(exml)
        xf.write('\n')
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
                '## Run failed. Cannot build yet. Please fix and retry')
            sys.exit(1)
        tdir = 'tfout' 
        if not os.path.exists(tdir):
            os.mkdir(tdir)
        self.makeXML()
        testdir = os.path.join('test-data')
        if not os.path.exists(testdir):
            os.mkdir(testdir)  # make tests directory
        for p in self.infiles:
            pth = p[IPATHPOS]
            dest = os.path.join(testdir, '%s.sample' % 
              p[ICLPOS])
            shutil.copyfile(pth, dest)
        for p in self.outfiles:
            pth = p[OCLPOS]
            dest = os.path.join(testdir, '%s.sample' % 
              p[OCLPOS])
            shutil.copyfile(pth, dest)  
            dest = os.path.join(tdir, '%s.%s' % (p[OCLPOS],p[OFMTPOS]))
            shutil.copyfile(pth, dest)              
        if os.path.exists(self.tlog) and os.stat(self.tlog).st_size > 0:
            shutil.copyfile(self.tlog, os.path.join(
                testdir, 'test1_log.txt'))
        stname = os.path.join(tdir, '%s.txt' % (self.sfile))
        if not os.path.exists(stname):
            shutil.copyfile(self.sfile, stname)
        xtname = os.path.join(tdir, "%s.txt" % (self.xmlfile))
        if not os.path.exists(xtname):
            shutil.copyfile(self.xmlfile, xtname)
        tarpath = "new_tool_gz"
        tar = tarfile.open(tarpath, "w:gz")
        tar.add(tdir, recursive=True, arcname='%s' % self.tool_name)
        tar.close()
        tardir = 'tardir'
        if not os.path.exists(tardir):
            os.mkdir(tardir)
        dest = os.path.join(tardir,tarpath)
        shutil.copyfile(tarpath, dest)
        # shutil.rmtree(tdir)
        # TODO: replace with optional direct upload to local toolshed?
        return retval

    def run(self):
        """
        Some devteam tools have this defensive stderr read so I'm keeping with the faith
        Feel free to update.
        """
        logging.debug('run cl=%s' % str(self.cl))
        scl = ' '.join(self.cl)
        err = None
        if self.args.parampass != '0':
            ste = open(self.elog, 'wb')
            sto = open(self.tlog, 'wb')
            sto.write(
                bytes('## Executing Toolfactory generated command line = %s\n' % scl, "utf8"))
            sto.flush()
            p = subprocess.run(self.cl, shell=False, stdout=sto,
                               stderr=ste)
            sto.close()
            ste.close()
            tmp_stderr = open(self.elog, 'rb')
            err = ''
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
            sti = open(self.infiles[0][IPATHPOS], 'rb')
            sto = open(self.outfiles[0][OCLPOS], 'wb')
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
        logging.debug('run done')
        return retval


def main():
    """
    This is a Galaxy wrapper. It expects to be called by a special purpose tool.xml as:
    <command interpreter="python">rgBaseScriptWrapper.py --script_path "$scriptPath" --tool_name "foo" --interpreter "Rscript"
    </command>
    """
    parser = argparse.ArgumentParser()
    a = parser.add_argument
    a('--script_path', default='')
    a('--tool_name', default=None)
    a('--interpreter_name', default=None)
    a('--interpreter_version', default=None)
    a('--exe_package', default=None)
    a('--exe_package_version', default=None)
    a('--input_files', default=[], action="append")
    a('--output_files', default=[], action="append")
    a('--user_email', default='Unknown')
    a('--bad_user', default=None)
    a('--make_Tool', default=None)
    a('--help_text', default=None)
    a('--tool_desc', default=None)
    a('--tool_version', default=None)
    a('--citations', default=None)
    a('--additional_parameters', action='append', default=[])
    a('--edit_additional_parameters', action="store_true", default=False)
    a('--parampass', default="positional")
    a('--tfout', default="./tfout")
    args = parser.parse_args()
    assert not args.bad_user, 'UNAUTHORISED: %s is NOT authorized to use this tool until Galaxy admin adds %s to "admin_users" in the Galaxy configuration file' % (
        args.bad_user, args.bad_user)
    assert args.tool_name, '## Tool Factory expects a tool name - eg --tool_name=DESeq'
    assert (args.interpreter_name or args.exe_package), '## Tool Factory wrapper expects an interpreter - eg --interpreter_name=Rscript or an executable package findable by the dependency management package'
    assert args.exe_package or (len(args.script_path) > 0 and os.path.isfile(
        args.script_path)), '## Tool Factory wrapper expects a script path - eg --script_path=foo.R if no executable'
    args.input_files = [x.replace('"', '').replace("'", '')
                        for x in args.input_files]
    # remove quotes we need to deal with spaces in CL params
    for i, x in enumerate(args.additional_parameters):
        args.additional_parameters[i] = args.additional_parameters[i].replace(
            '"', '')
    os.makedirs(args.tfout, exist_ok=True)
    r = ScriptRunner(args)
    if args.make_Tool:
        retcode = r.makeTooltar()
    else:
        retcode = r.run()
    if retcode:
        sys.exit(retcode)  # indicate failure to job runner


if __name__ == "__main__":
    main()
