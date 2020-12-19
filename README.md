## Breaking news! Docker container at https://github.com/fubar2/toolfactory-galaxy-docker recommended as at December 2020

## This is the original ToolFactory suitable for non-docker situations. Please use the docker container if you can because it's integrated with a Toolshed...

# WARNING

Install this tool to a throw-away private Galaxy or Docker container ONLY!

Please NEVER on a public or production instance where a hostile user may
be able to gain access if they can acquire an administrative account login.

It only runs for server administrators - the ToolFactory tool will refuse to execute for an ordinary user since
it can install new tools to the Galaxy server it executes on! This is not something you should allow other than
on a throw away instance that is protected from potentially hostile users.

## Short Story

Galaxy is easily extended to new applications by adding a new tool. Each new scientific computational package added as
a tool to Galaxy requires an XML document describing how the application interacts with Galaxy.
This is sometimes termed "wrapping" the package because the instructions tell Galaxy how to run the package
as a new Galaxy tool. Any tool that has been wrapped is readily available to all the users through a consistent
and easy to use interface once installed in the local Galaxy server.

Most Galaxy tool wrappers have been manually prepared by skilled programmers, many using Planemo because it
automates much of the boilerplate and makes the process much easier.
The ToolFactory (TF) now uses Planemo under the hood for testing, but hides the command
line complexities. The user will still need appropriate skills in terms of describing the interface between
Galaxy and the new application, but will be helped by a Galaxy tool form to collect all the needed
settings, together with automated testing and uploading to a toolshed with optional local installation.


## ToolFactory generated tools are ordinary Galaxy tools

A TF generated tool that passes the Planemo test is ready to publish in any Galaxy Toolshed and ready to install in any running Galaxy instance.
They are fully workflow compatible and work exactly like any hand-written tool. The user can select input files of the specified type(s) from their
history and edit each of the specified parameters. The tool form will show all the labels and help text supplied when the tool was built. When the tool
is executed, the dependent binary or script will be passed all the i/o files and parameters as specified, and will write outputs to the specified new
history datasets - just like any other Galaxy tool.

## Models for tool command line construction

The key to turning any software package into a Galaxy tool is the automated construction of a suitable command line.

The TF can build a new tool that will allow the tool user to select input files from their history, set any parameters and when run will send the
new output files to the history as specified when the tool builder completed the form and built the new tool.

That tool can contain instructions to run any Conda dependency or a system executable like bash. Whether a bash script you have written or
a Conda package like bwa, the executable will expect to find settings for input, output and parameters on a command line.

IThese are often passed as "--name value" (argparse style) or in a fixed order (positional style).

The ToolFactory allows either, or for "filter" applications that process input from STDIN and write processed output to STDOUT.

The simplest tool model wraps a simple script or Conda dependency package requiring only input and output files, with no user supplied settings illustrated by
the Tacrev demonstration tool found in the Galaxy running in the ToolFactory docker container. It passes a user selected input file from the current history on STDIN
to a bash script. The bash script runs the unix tac utility (reverse cat) piped to the unix rev (reverse lines in a text file) utility. It's a one liner:

`tac | rev`

The tool building form allows naming zero or more Conda package name(s) and version(s) and the supply of a script to be executed by either a system
executable like ``bash`` or the first of any named Conda dependency package/version. Tacrev uses a tiny bash script shown above and uses the system
bash. Conda bash can be specified if it is important to use the same version consistently for the tool.

On the tool form, the repeat section allowing zero or more input files was set to be a text file to be selected by the tool user and
in the repeat section allowing one or more outputs, a new output file with special value `STDOUT` as the positional parameter, causes the TF to
generate a command to capture STDOUT and send it to the new history file containing the reversed input text.

By reversed, we mean really, truly reversed.

That simple model can be made much more complicated, and can pass inputs and outputs as named or positional parameters,
to allow more complicated scripts or dependent binaries that require:

1. Any number of input data files selected by the user from existing history data
2. Any number of output data files written to the user's history
3. Any number of user supplied parameters. These can be passed as command line arguments to the script or the dependency package. Either
positional or named (argparse) style command line parameter passing can be used.

More complex models can be seen in the Sedtest, Pyrevpos and Pyrevargparse tools illustrating positional and argparse parameter passing.

The most complex demonstration is the Planemo advanced tool tutorial BWA tool. There is one version using a command-override to implement
exactly the same command structure in the Planemo tutorial. A second version uses a bash script and positional parameters to achieve the same
result. Some tool builders may find the bash version more familiar and cleaner but the choice is yours.

## Overview

Steps in building a new Galaxy tool are all conducted through Galaxy running in the docker container:

1. Login to the Galaxy running in the container at http://localhost:8080 using an admin account. They are specified in config/galaxy.yml and
    in the documentation at
    and the ToolFactory will error out and refuse to run for non-administrative tool builders as a minimal protection from opportunistic hostile use.

2. Start the TF and fill in the form, providing sample inputs and parameter values to suit the Conda package being wrapped.

3. Execute the tool to create a new XML tool wrapper using the sample inputs and parameter settings for the inbuilt tool test. Planemo runs twice.
    firstly to generate the test outputs and then to perform a proper test. The completed toolshed archive is written to the history
    together with the planemo test report. Optionally the new tool archive can be uploaded
    to the toolshed running in the same container (http://localhost:9009) and then installed inside the Galaxy in the container for further testing.

4. If the test fails, rerun the failed history job and correct errors on the tool form before rerunning until everything works correctly.

![IHello example ToolFactory tool form](files/hello_toolfactory_form.png?raw=true "Part of the Hello world example ToolFactory tool form")


## Planning and building new Galaxy tool wrappers.

It is best to have all the required planning done to wrap any new script or binary before firing up the TF.
Conda is the only current dependency manager supported. Before starting, at the very least, the tool builder will need
to know the required software package name in Conda and the version to use, how the command line for
the package must be constructed, and there must be sample inputs in the working history for each of the required data inputs
for the package, together with values for every parameter to suit these sample inputs. These are required on the TF form
for preparing the inbuilt tool test. That test is run using Planemo, as part of the tool generation process.

A new tool is specified by filling in the usual Galaxy tool form.

The form starts with a new tool name. Most tools will need dependency packages and versions
for the executable. Only Conda is currently supported.

If a script is needed, it can be pasted into a text box and the interpreter named. Available system executables
can be used such as bash, or an interpreter such as python, perl or R can be nominated as conda dependencies
to ensure reproducible analyses.

The tool form will be generated from the input data and the tool builder supplied parameters. The command line for the
executable is built using positional or argparse (named e.g. --input_file /foo/baz) style
parameters and is completely dependent on the executable. These can include:

1. Any number of input data sets needed by the executable. Each appears to the tool user on the run form and is included
on the command line for the executable. The tool builder must supply a small representative sample for each one as
an input for the automated tool test.

2. Any number of output data sets generated by the package can be added to the command line and will appear in
the user's history at the end of the job

3. Any number of text or numeric parameters. Each will appear to the tool user on the run form and are included
on the command line to the executable. The tool builder must supply a suitable representative value for each one as
the value to be used for the automated tool test.

Once the form is completed, executing the TF will build a new XML tool wrapper
including a functional test based on the sample settings and data.

If the Planemo test passes, the tool can be optionally uploaded to the local Galaxy used in the image for more testing.

A local toolshed runs inside the container to allow an automated installation, although any toolshed and any accessible
Galaxy can be specified for this process by editing the default URL and API keys to provide appropriate credentials.

## Generated Tool Dependency management

Conda is used for all dependency management although tools that use system utilities like sed, bash or awk
may be available on job execution nodes. Sed and friends are available as Conda (conda-forge) dependencies if necessary.
Versioned Conda dependencies are always baked-in to the tool and will be used for reproducible calculation.

## Requirements

These are all managed automagically. The TF relies on galaxyxml to generate tool xml and uses ephemeris and
bioblend to load tools to the toolshed and to Galaxy. Planemo is used for testing and runs in a biocontainer currently at
https://quay.io/fubar2/planemo-biocontainer

## Caveats

This docker image requires privileged mode so exposes potential security risks if hostile tool builders gain access.
Please, do not run it in any situation where that is a problem - never, ever on a public facing Galaxy server.
On a laptop or workstation should be fine in a non-hostile environment.


## Example generated XML

For the bwa-mem example, a supplied bash script is included as a configfile and so has escaped characters.
```
<tool name="bwatest" id="bwatest" version="0.01">
  <!--Cite: Creating re-usable tools from scripts doi:10.1093/bioinformatics/bts573-->
  <!--Source in git at: https://github.com/fubar2/toolfactory-->
  <!--Created by admin@galaxy.org at 30/11/2020 07:12:10 using the Galaxy Tool Factory.-->
  <description>Planemo advanced tool building sample bwa mem mapper as a ToolFactory demo</description>
  <requirements>
    <requirement version="0.7.15" type="package">bwa</requirement>
    <requirement version="1.3" type="package">samtools</requirement>
  </requirements>
  <configfiles>
    <configfile name="runme"><![CDATA[
REFFILE=\$1
FASTQ=\$2
BAMOUT=\$3
rm -f "refalias"
ln -s "\$REFFILE" "refalias"
bwa index -a is "refalias"
bwa mem -t "2"  -v 1 "refalias" "\$FASTQ"  > tempsam
samtools view -Sb tempsam > temporary_bam_file.bam
samtools sort -o "\$BAMOUT" temporary_bam_file.bam

]]></configfile>
  </configfiles>
  <version_command/>
  <command><![CDATA[bash
$runme
$input1
$input2
$bam_output]]></command>
  <inputs>
    <param optional="false" label="Reference sequence for bwa to map the fastq reads against" help="" format="fasta" multiple="false" type="data" name="input1" argument="input1"/>
    <param optional="false" label="Reads as fastqsanger to align to the reference sequence" help="" format="fastqsanger" multiple="false" type="data" name="input2" argument="input2"/>
  </inputs>
  <outputs>
    <data name="bam_output" format="bam" label="bam_output" hidden="false"/>
  </outputs>
  <tests>
    <test>
      <output name="bam_output" value="bam_output_sample" compare="sim_size" format="bam" delta_frac="0.1"/>
      <param name="input1" value="input1_sample"/>
      <param name="input2" value="input2_sample"/>
    </test>
  </tests>
  <help><![CDATA[

**What it Does**

Planemo advanced tool building sample bwa mem mapper

Reimagined as a bash script for a ToolFactory demonstration


------

Script::

    REFFILE=$1
    FASTQ=$2
    BAMOUT=$3
    rm -f "refalias"
    ln -s "$REFFILE" "refalias"
    bwa index -a is "refalias"
    bwa mem -t "2"  -v 1 "refalias" "$FASTQ"  > tempsam
    samtools view -Sb tempsam > temporary_bam_file.bam
    samtools sort -o "$BAMOUT" temporary_bam_file.bam

]]></help>
</tool>

```



## More Explanation

The TF is an unusual Galaxy tool, designed to allow a skilled user to make new Galaxy tools.
It appears in Galaxy just like any other tool but outputs include new Galaxy tools generated
using instructions provided by the user and the results of Planemo lint and tool testing using
small sample inputs provided by the TF user. The small samples become tests built in to the new tool.

It offers a familiar Galaxy form driven way to define how the user of the new tool will
choose input data from their history, and what parameters the new tool user will be able to adjust.
The TF user must know, or be able to read, enough about the tool to be able to define the details of
the new Galaxy interface and the ToolFactory offers little guidance on that other than some examples.

Tools always depend on other things. Most tools in Galaxy depend on third party
scientific packages, so TF tools usually have one or more dependencies. These can be
scientific packages such as BWA or scripting languages such as Python and are
managed by Conda. If the new tool relies on a system utility such as bash or awk
where the importance of version control on reproducibility is low, these can be used without
Conda management - but remember the potential risks of unmanaged dependencies on computational
reproducibility.

The TF user can optionally supply a working script where scripting is
required and the chosen dependency is a scripting language such as Python or a system
scripting executable such as bash. Whatever the language, the script must correctly parse the command line
arguments it receives at tool execution, as they are defined by the TF user. The
text of that script is "baked in" to the new tool and will be executed each time
the new tool is run. It is highly recommended that scripts and their command lines be developed
and tested until proven to work before the TF is invoked. Galaxy as a software development
environment is actually possible, but not recommended being somewhat clumsy and inefficient.

Tools nearly always take one or more data sets from the user's history as input. TF tools
allow the TF user to define what Galaxy datatypes the tool end user will be able to choose and what
names or positions will be used to pass them on a command line to the package or script.

Tools often have various parameter settings. The TF allows the TF user to define how each
parameter will appear on the tool form to the end user, and what names or positions will be
used to pass them on the command line to the package. At present, parameters are limited to
simple text and number fields. Pull requests for other kinds of parameters that galaxyxml
can handle are welcomed.

Best practice Galaxy tools have one or more automated tests. These should use small sample data sets and
specific parameter settings so when the tool is tested, the outputs can be compared with their expected
values. The TF will automatically create a test for the new tool. It will use the sample data sets
chosen by the TF user when they built the new tool.

The TF works by exposing *unrestricted* and therefore extremely dangerous scripting
to all designated administrators of the host Galaxy server, allowing them to
run scripts in R, python, sh and perl. For this reason, a Docker container is
available to help manage the associated risks.

## Scripting uses

To use a scripting language to create a new tool, you must first prepared and properly test a script. Use small sample
data sets for testing. When the script is working correctly, upload the small sample datasets
into a new history, start configuring a new ToolFactory tool, and paste the script into the script text box on the TF form.

### Outputs

The TF will generate the new tool described on the TF form, and test it
using planemo. Optionally if a local toolshed is running, it can be used to
install the new tool back into the generating Galaxy.

A toolshed is built in to the Docker container and configured
so a tool can be tested, sent to that toolshed, then installed in the Galaxy
where the TF is running using the default toolshed and Galaxy URL and API keys.

Once it's in a ToolShed, it can be installed into any local Galaxy server
from the server administrative interface.

Once the new tool is installed, local users can run it - each time, the
package and/or script that was supplied when it was built will be executed with the input chosen
from the user's history, together with user supplied parameters. In other words, the tools you generate with the
TF run just like any other Galaxy tool.

TF generated tools work as normal workflow components.


## Limitations

The TF is flexible enough to generate wrappers for many common scientific packages
but the inbuilt automation will not cope with all possible situations. Users can
supply overrides for two tool XML segments - tests and command and the BWA
example in the supplied samples workflow illustrates their use. It does not deal with
repeated elements or conditional parameters such as allowing a user to choose to see "simple"
or "advanced" parameters (yet) and there will be plenty of packages it just
won't cover - but it's a quick and efficient tool for the other 90% of cases. Perfect for
that bash one liner you need to get that workflow functioning correctly for this
afternoon's demonstration!

## Installation

The Docker container https://github.com/fubar2/toolfactory-galaxy-docker/blob/main/README.md
is the best way to use the TF because it is preconfigured
to automate new tool testing and has a built in local toolshed where each new tool
is uploaded. If you grab the docker container, it should just work after a restart and you
can run a workflow to generate all the sample tools. Running the samples and rerunning the ToolFactory
jobs that generated them allows you to add fields and experiment to see how things work.

It can be installed like any other tool from the Toolshed, but you will need to make some
configuration changes (TODO write a configuration). You can install it most conveniently using the
administrative "Search and browse tool sheds" link. Find the Galaxy Main
toolshed at https://toolshed.g2.bx.psu.edu/ and search for the toolfactory
repository in the Tool Maker section. Open it and review the code and select the option to install it.

If not already there please add:

```
<datatype extension="tgz" type="galaxy.datatypes.binary:Binary" mimetype="multipart/x-gzip" subclass="True" />
```

to your local config/data_types_conf.xml.


## Restricted execution

The tool factory tool itself will ONLY run for admin users -
people with IDs in config/galaxy.yml "admin_users".

*ONLY admin_users can run this tool*

That doesn't mean it's safe to install on a shared or exposed instance - please don't.

## Generated tool Security

Once you install a generated tool, it's just
another tool - assuming the script is safe. They just run normally and their
user cannot do anything unusually insecure but please, practice safe toolshed.
Read the code before you install any tool. Especially this one - it is really scary.

## Attribution

Creating re-usable tools from scripts: The Galaxy Tool Factory
Ross Lazarus; Antony Kaspi; Mark Ziemann; The Galaxy Team
Bioinformatics 2012; doi: 10.1093/bioinformatics/bts573

http://bioinformatics.oxfordjournals.org/cgi/reprint/bts573?ijkey=lczQh1sWrMwdYWJ&keytype=ref

