#!/usr/bin/env python3
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
# galaxyxml now generates the tool xml and we no longer support automatic HTML file creation.



import sys
import subprocess
import shutil
import os
import time 
import tempfile
import argparse
import tarfile
import re
import math
import galaxyxml.tool as gxt
import galaxyxml.tool.parameters as gxtp
import logging


progname = os.path.split(sys.argv[0])[1] 
myversion = 'V2.1 July 2020' 
verbose = True
debug = True
toolFactoryURL = 'https://github.com/fubar2/toolfactory'
ourdelim = '~~~'


def timenow():
	"""return current time as a string
	"""
	return time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(time.time()))

def quote_non_numeric(s):
	"""return a prequoted string for non-numerics
	useful for perl and Rscript parameter passing?
	"""
	try:
		res = float(s)
		return s
	except ValueError:
		return '"%s"' % s

html_escape_table = {
	 "&": "&amp;",
	 ">": "&gt;",
	 "<": "&lt;",
	 "$": "\$"
	 }

def html_escape(text):
	 """Produce entities within text."""
	 return "".join(html_escape_table.get(c,c) for c in text)


def html_unescape(text):
	 """Revert entities within text. Multiple character targets so use replace"""
	 t = text.replace('&amp;','&').replace('&gt;','>').replace('&lt;','<').replace('\$','$')
	 return t

def parse_citations(citations_text):
	"""
	"""
	citations = [c for c in citations_text.split("**ENTRY**") if c.strip()]
	citation_tuples = []
	for citation in citations:
		if citation.startswith("doi"):
			citation_tuples.append( ("doi", citation[len("doi"):].strip() ) )
		else:
			citation_tuples.append( ("bibtex", citation[len("bibtex"):].strip() ) )
	return citation_tuples

	
class ScriptRunner:
	"""Wrapper for an arbitrary script
	uses galaxyxml
	
	"""


	def __init__(self,args=None):
		"""
		cleanup inputs, setup some outputs
		
		"""
		self.logf = open('/home/ross/rossgit/toolfactory/tmp/toolfactory.log','w')
		lastclredirect = None
		self.cl = []
		aCL = self.cl.append
		if args.output_dir: # simplify for the tool tarball
			os.chdir(args.output_dir)
		self.args = args
		self.tool_name = re.sub('[^a-zA-Z0-9_]+', '', args.tool_name) # a sanitizer now does this but..
		self.tool_id = self.tool_name
		self.xmlfile = '%s.xml' % self.tool_name
		if self.args.interpreter_name == "Executable": # binary - no need
			aCL(self.args.exe_package)  # this little CL will just run
		else: # a script has been provided
			rx = open(self.args.script_path,'r').readlines()
			rx = [x.rstrip() for x in rx] # remove pesky dos line endings if needed
			self.script = '\n'.join(rx)
			fhandle,self.sfile = tempfile.mkstemp(prefix=self.tool_name,suffix=".%s" % (args.interpreter_name))
			tscript = open(self.sfile,'w') # use self.sfile as script source for Popen
			tscript.write(self.script)
			tscript.close()
			self.indentedScript = "  %s" % '\n'.join([' %s' % html_escape(x) for x in rx]) # for restructured text in help
			self.escapedScript = "%s" % '\n'.join([' %s' % html_escape(x) for x in rx])
			if self.args.interpreter_name == 'python': # work around - actually python3 now but for conda deps....
				aCL('python3')
			else:
				aCL(self.args.interpreter_name)
			aCL(self.sfile)
		self.elog = os.path.join(self.args.output_dir,"%s_error.log" % self.tool_name)
		if args.output_dir: # may not want these complexities 
			self.tlog = os.path.join(self.args.output_dir,"%s_runner.log" % self.tool_name)
			art = '%s.%s' % (self.tool_name,args.interpreter_name)
			artpath = os.path.join(self.args.output_dir,art) # need full path
			artifact = open(artpath,'w') # use self.sfile as script source for Popen
			artifact.write(self.script)
			artifact.close()
		self.infile_paths = []
		self.infile_format = []
		self.infile_cl = []
		self.infile_label = []
		self.infile_help = []
		if self.args.input_files:
			aif = [x.split(ourdelim) for x in self.args.input_files]
			laif = list(map(list, zip(*aif))) # transpose the input_files array --input_files="$input_files~~~$CL~~~$input_formats~~~$input_label~~~$input_help"
			self.infile_paths,self.infile_cl,self.infile_format,self.infile_label,self.infile_help = laif
			self.infile_name = []
			for i,scl in enumerate(self.infile_cl): # positionals have integers indicating order - need valid internal names
				if scl.isdigit():
					scl = 'input%s' % scl
				if scl.upper() in ['STDOUT','STDIN']:
					scl = 'input%d' % (i+1)
				self.infile_name.append(scl) # make a list of internal names for each input file
		clsuffix = [] # list all (cl param) pairs - positional needs sorting by cl index
		clsuffix.append([self.args.output_cl,self.args.output_tab])		
		if self.args.parampass == '0': # only need two
			aCL('<')
			aCL('%s' % self.infile_paths[0])
			aCL('>')
			aCL('%s' % self.args.output_tab)
		else:
			for i,p in enumerate(self.infile_paths):
				clsuffix.append([self.infile_cl[i],p]) # decorator is cl - sort for positional
			for p in self.args.additional_parameters:
				psplit = p.split(ourdelim)
				pform = psplit[5]
				if pform == 'STDOUT':
					lastclredirect = ['>',psplit[1]]
				else:
					clsuffix.append([pform,psplit[1]]) # cl,value
			clsuffix.sort()
			if self.args.parampass == "positional":
				plist = [] # need to decorate with CL and sort
				# inputs in order then params in order TODO fix ordering using self.infile_cl
				for (k,v) in clsuffix:
					if ' ' in v:
						aCL("v")
					else:
						aCL(v)
			elif self.args.parampass == "argparse":
				# inputs then params in argparse named form
				for (k,v) in clsuffix:
					if ' ' in v:
						aCL('--%s' % k)
						aCL('"%s"' % v)
					else:
						aCL('--%s' % k)
						aCL('%s' % v)
			if lastclredirect:
				for v in lastclredirect:
					aCL(v) # add the stdout parameter last
		self.outFormats = args.output_format
		self.inputFormats = args.input_formats
		self.test1Output = '%s_test1_output.xls' % self.tool_name
		self.test1HTML = '%s_test1_output.html' % self.tool_name
		self.logf.write('### cl=%s\n' % str(' '.join(self.cl)))
		
	def makeXML(self):
		"""
		Create a Galaxy xml tool wrapper for the new script as a string to write out
		It calls this python code you are reading and runs the script or executable with
		parameters as required.
		
		WRONG
		<command interpreter="python"><![CDATA[$runMe --infile $infile
--prefix $prefix
output1 $output1]]></command>
		"""
		# need interp and executable (?script) or else executable only
		if self.args.interpreter_name:
			exe = "$runMe" # our dynamic script from the tool builder
			interp = self.args.interpreter_name
		else:
			interp = None
			exe = self.args.exe_package
		assert exe != None, 'No interpeter or executable passed in to makeXML'
		tool = gxt.Tool(self.args.tool_name,self.tool_id,self.args.tool_version,self.args.tool_desc,exe)
		if interp:
			tool.interpreter=interp
		if self.args.help_text:
			helptext = open(self.args.help_text,'r').readlines()
			helptext = [html_escape(x) for x in helptext] # must html escape here too - thanks to Marius van den Beek
			tool.help = ''.join([x for x in helptext])
		else:
				tool.help = 'Please ask the tool author (%s) for help as none was supplied at tool generation\n' % (user_email)
		tool.version_command = None # do not want
		inputs = gxtp.Inputs()
		outputs = gxtp.Outputs()
		requirements = gxtp.Requirements()
		testparam = []
		is_positional = (self.args.parampass == 'positional')
		if self.args.include_dependencies == "yes":
			requirements.append(gxtp.Requirement('package', 'ghostscript'))
			requirements.append(gxtp.Requirement('package', 'graphicsmagick'))
		if self.args.interpreter_name:
			if self.args.interpreter_name == 'python': # always needed for this runner script
				requirements.append(gxtp.Requirement('package', 'python',self.args.interpreter_version))
			elif not self.args.interpreter_name in ['bash','sh']:
				requirements.append(gxtp.Requirement('package', self.args.interpreter_name,self.args.interpreter_version))
		else:
			if self.args.exe_package: # uses exe not interpreter
				requirements.append(gxtp.Requirement('package', self.args.exe_package,self.args.exe_package_version))
		tool.requirements = requirements
		for i,infpath in enumerate(self.infile_paths):
			assert len(self.infile_name[i]) > 0,'Newname supplied for input parameter %s is empty' % self.infile_label[i]
			if self.args.parampass == 0:
				assert len(self.infile_name) == 1,'Maximum one "<" if parampass is 0 - more than one input files supplied'
			newname = self.infile_name[i]
			if len(newname) > 1:
				ndash = 2
			else:
				ndash = 1	
			aninput = gxtp.DataParam(self.infile_name[i],optional=False, label=self.infile_label[i], help=self.infile_help[i], \
				format=self.infile_format[i],multiple=False,num_dashes=ndash)
			if self.args.parampass == '0':
				aninput.command_line_override = '< $%s' % self.infile_name[i]
			aninput.positional = is_positional
			inputs.append(aninput)
		for parm in self.args.additional_parameters:
			newname,newval,newlabel,newhelp,newtype,newcl = parm.split(ourdelim)
			assert len(newname) > 0,'Newname supplied for parameter %s is empty' % newlabel
			if len(newname) > 1:
				ndash = 2
			else:
				ndash = 1	
			if newtype == "text":
				aparm = gxtp.TextParam(newname,label=newlabel,help=newhelp,value=newval,num_dashes=ndash)
			elif newtype == "integer":
				aparm = gxtp.IntegerParam(newname,label=newname,help=newhelp,value=newval,num_dashes=ndash)
			elif newtype == "float":
				aparm = gxtp.FloatParam(newname,label=newname,help=newhelp,value=newval,num_dashes=ndash)
			else:
				raise ValueError('Unrecognised parameter type "%s" for additional parameter %s in makeXML' % (newtype,psplit[0]))
			aparm.positional = is_positional
			inputs.append(aparm)
			tparm = gxtp.TestParam(newname,value=newval)
			testparam.append(tparm)
		tool.inputs = inputs
		configfiles = gxtp.Configfiles()
		configfiles.append(gxtp.Configfile(name="runMe",text=self.script))
		tool.configfiles = configfiles
		if self.args.output_tab:
			aparm = gxtp.OutputData(self.args.output_cl, format=self.args.output_format)
			if is_positional:
				aparm.command_line_override = '> $output1' 
			aparm.positional = is_positional
			outputs.append(aparm)
		tool.outputs = outputs
		tests = gxtp.Tests()
		test_a = gxtp.Test()
		if is_positional:
			param = gxtp.TestParam('input1',value='input1.%s' % self.infile_format[0],ftype=self.infile_format[0])
		else:
			param = gxtp.TestParam(self.infile_name[0],value='%s.%s' % (self.infile_name[0],self.infile_format[0]),ftype=self.infile_format[0])
		test_a.append(param)	
		param = gxtp.TestParam('job_name', value='test_a')
		test_a.append(param)
		param = gxtp.TestParam('runMe', value="$runMe")
		test_a.append(param)
		for aparam in testparam:
			test_a.append(aparam)
		test_out = gxtp.TestOutput(name=self.args.output_tab, value=self.test1Output)
		test_a.append(test_out)
		tests.append(test_a)		
		tool.tests = tests
		tool.add_comment('Created by %s at %s using the Galaxy Tool Factory.' % (self.args.user_email,timenow()))
		tool.add_comment('Source in git at: %s' % (toolFactoryURL))
		tool.add_comment('Cite: Creating re-usable tools from scripts doi: 10.1093/bioinformatics/bts573')
		exml = tool.export()
		xf = open(self.xmlfile,'w')
		xf.write(exml)
		xf.write('\n')
		xf.close()
		self.logf.write('xml=%s\n' % exml)
		# ready for the tarball


	def makeTooltar(self):
		"""
		a tool is a gz tarball with eg
		/toolname/tool.xml /toolname/tool.py /toolname/test-data/test1_in.foo ...
		"""
		retval = self.run()
		if retval:
			sys.stderr.write('## Run failed. Cannot build yet. Please fix and retry')
			sys.exit(1)
		tdir = 'tdir_%s' % self.tool_name
		if not os.path.exists(tdir):
			os.mkdir(tdir)
		self.makeXML()
		if self.args.help_text:
			hlp = open(self.args.help_text,'r').read()
		else:
			hlp = 'Please ask the tool author for help as none was supplied at tool generation\n'
		readme_dict = {'readme':hlp,'interpreter_name':self.args.interpreter_name,'interpreter_version':self.args.interpreter_version}
		testdir = os.path.join(tdir,'test-data')
		if not os.path.exists(testdir):
			os.mkdir(testdir) # make tests directory
		for i,infile in enumerate(self.infile_paths):
			dest = os.path.join(testdir,'%s.%s' % (self.infile_name[i],self.infile_format[i]))
			if infile != dest:
				shutil.copyfile(infile,dest)
		if self.args.output_tab and os.path.exists(self.args.output_tab):
			shutil.copyfile(self.args.output_tab,os.path.join(testdir,self.test1Output))
		else:
			print('#### no output_tab %s exists' % self.args.output_tab)
		if self.args.output_dir:
			if os.path.exists(self.tlog):
				shutil.copyfile(self.tlog,os.path.join(testdir,'test1_out.log'))
		stname = os.path.join(tdir,self.sfile)
		if not os.path.exists(stname):
			shutil.copyfile(self.sfile, stname)
		xtname = os.path.join(tdir,self.xmlfile)
		if not os.path.exists(xtname):
			shutil.copyfile(self.xmlfile,xtname)
		tarpath = "%s.tar.gz" % self.tool_name
		tar = tarfile.open(tarpath, "w:gz")
		tar.add(tdir,recursive=True,arcname='%s' % self.tool_name)
		tar.close()
		shutil.copyfile(tarpath,self.args.new_tool)
		shutil.rmtree(tdir)
		## TODO: replace with optional direct upload to local toolshed?
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
			ste = open(self.elog,'wb')
			sto = open(self.tlog,'wb')
			sto.write(bytes('## Executing Toolfactory generated command line = %s\n' % scl,"utf8"))
			sto.flush()
			p = subprocess.run(self.cl,shell=False,stdout=sto,stderr=ste,cwd=self.args.output_dir)
			sto.close()
			ste.close()
			tmp_stderr = open(self.elog, 'rb' )
			err = ''
			buffsize = 1048576
			try:
				while True:
					err += str(tmp_stderr.read( buffsize ))
					if not err or len( err ) % buffsize != 0:
						break
			except OverflowError:
				pass
			tmp_stderr.close()
			retval = p.returncode
		else: # work around special case of simple scripts that take stdin and write to stdout
			sti = open(self.infile_paths[0],'rb')
			sto = open(self.args.output_tab,'wb')
			p = subprocess.run(self.cl, shell=False, stdout=sto,stdin=sti) # must use shell to redirect
			retval = p.returncode
			sto.close()
			sti.close()
		if self.args.output_dir:
			if p.returncode != 0 and err: # problem
				sys.stderr.write(err)
		logging.debug('run done')
		return retval

  

def main():
	u = """
	This is a Galaxy wrapper. It expects to be called by a special purpose tool.xml as:
	<command interpreter="python">rgBaseScriptWrapper.py --script_path "$scriptPath" --tool_name "foo" --interpreter "Rscript"
	</command>
	"""
	parser = argparse.ArgumentParser()
	a = parser.add_argument
	a('--script_path',default='')
	a('--tool_name',default=None)
	a('--interpreter_name',default=None)
	a('--interpreter_version',default=None)
	a('--exe_package',default=None)
	a('--exe_package_version',default=None)
	a('--output_dir',default='./')
	a('--input_files',default=[], action="append") # these are "galaxypath,metadataname" pairs
	a("--input_formats",default="tabular")
	a('--output_tab',default=None)
	a('--output_format',default='tabular')
	a('--output_cl',default=None)
	a('--user_email',default='Unknown')
	a('--bad_user',default=None)
	a('--make_Tool',default=None)
	a('--help_text',default=None)
	a('--tool_desc',default=None)
	a('--new_tool',default=None)
	a('--tool_version',default=None)
	a('--include_dependencies',default=None)   
	a('--citations',default=None)
	a('--additional_parameters', dest='additional_parameters', action='append', default=[])
	a('--edit_additional_parameters', action="store_true", default=False)
	a('--parampass',default="positional")   
	args = parser.parse_args()
	assert not args.bad_user,'UNAUTHORISED: %s is NOT authorized to use this tool until Galaxy admin adds %s to "admin_users" in the Galaxy configuration file' % (args.bad_user,args.bad_user)
	assert args.tool_name,'## Tool Factory expects a tool name - eg --tool_name=DESeq'
	assert args.interpreter_name,'## Tool Factory wrapper expects an interpreter - eg --interpreter_name=Rscript'
	assert len(args.script_path) > 0 and os.path.isfile(args.script_path),'## Tool Factory wrapper expects a script path - eg --script_path=foo.R'
	if args.output_dir:
		try:
			os.makedirs(args.output_dir)
		except:
			pass
	#logging.basicConfig(filename=os.path.join(args.output_dir,'toolfactory.log'),level=logging.DEBUG,format='%(asctime)s %(message)s',filemode='w')
	args.input_files = [x.replace('"','').replace("'",'') for x in args.input_files]
	for i,x in enumerate(args.additional_parameters): # remove quotes we need to deal with spaces in CL params
		args.additional_parameters[i] = args.additional_parameters[i].replace('"','')
	r = ScriptRunner(args)
	if args.make_Tool:
		retcode = r.makeTooltar()
	else:
		retcode = r.run()
	os.unlink(r.sfile)
	r.logf.close()
	if retcode:
		sys.exit(retcode) # indicate failure to job runner


if __name__ == "__main__":
	main()


