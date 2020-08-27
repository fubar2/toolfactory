**Breaking news! Docker container is recommended as at August 2020**

A Docker container can be built - see the docker directory.
It is highly recommended for isolation. It also has an integrated toolshed to allow installation of new tools back 
into the Galaxy being used to generate them. 

Built from quay.io/bgruening/galaxy:20.05 but updates the
Galaxy code to the dev branch - it seems to work fine with updated bioblend>=0.14
with planemo and the right version of gxformat2 needed by the ToolFactory (TF).

The runclean.sh script run from the docker subdirectory of your local clone of this repository
should create a container (eventually) and serve it at localhost:8080 with a toolshed at
localhost:9009.

Once it's up, please restart Galaxy in the container with 
```docker exec [container name] supervisorctl restart galaxy: ```
Jobs just do not seem to run properly otherwise and the next steps won't work!

The generated container includes a workflow and 2 sample data sets for the workflow

Load the workflow. Adjust the inputs for each as labelled. The perl example counts GC in phiX.fasta. 
The python scripts use the rgToolFactory.py as their input - any text file will work but I like the
recursion. The BWA example has some mitochondrial reads and reference. Run the workflow and watch.
This should fill the history with some sample tools you can rerun and play with.
Note that each new tool will have been tested using Planemo. In the workflow, in Galaxy.
Extremely cool to watch.

*WARNING before you start* 

 Install this tool on a throw-away private Galaxy or Docker container ONLY
 Please NEVER on a public or production instance
 
Please cite the resource at
http://bioinformatics.oxfordjournals.org/cgi/reprint/bts573?ijkey=lczQh1sWrMwdYWJ&keytype=ref
if you use this tool in your published work.

*Short Story*

Galaxy is easily extended to new applications by adding a new tool. Each new scientific computational package added as
a tool to Galaxy requires some special instructions to be written. This is sometimes termed "wrapping" an application
because the wrapper code instructs Galaxy how to make the third party package readily available to all Galaxy users. 
Most Galaxy tools have been manually prepared by skilled programmers, many using Planemo because it 
automates much of the basic boilerplate and makes the process much easier. The ToolFactory (TF) 
uses Planemo under the hood for many functions, but hides the command
line complexities from the TF user. 

*More Explanation*

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
usually managed by Conda. If the new tool relies on a system utility such as bash or awk 
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
parameter will appear on the tool form to the end user, and the names and positions will be
used to pass them on the command line to the package. At present, parameters are limited to
simple text and number fields. Pull requests for other kinds of parameters are welcomed.

Best practice Galaxy tools have one or more automated tests. These should use small sample data sets and
specific parameter settings so when the tool is tested, the outputs can be compared with their expected
values. The TF will automatically create a test for the new tool. It will use the sample data sets 
chosen by the TF user when they built the new tool.

The TF works by exposing *unrestricted* and therefore extremely dangerous scripting
to all designated administrators of the host Galaxy server, allowing them to
run scripts in R, python, sh and perl. For this reason, a Docker container is
available to help manage the associated risks.

*Scripting uses*

To use a scripting language to create a new tool, you must first prepared and properly test a script. Use small sample
data sets for testing. When the script is working correctly, upload the small sample datasets
into a new history, start configuring a new ToolFactory tool, and paste the script into the script text box on the TF form.

*Outputs*

Once the script runs sucessfully, a new Galaxy tool that runs your script
can be generated. Select the "generate" option and supply some help text and
names. The new tool will be generated in the form of a new Galaxy datatype
*tgz* - as the name suggests, it's an archive ready to upload to a
Galaxy ToolShed as a new tool repository.


Once it's in a ToolShed, it can be installed into any local Galaxy server
from the server administrative interface.

Once the new tool is installed, local users can run it - each time, the script
that was supplied when it was built will be executed with the input chosen
from the user's history. In other words, the tools you generate with the
ToolFactory run just like any other Galaxy tool,but run your script every time.

Tool factory tools are perfect for workflow components. One input, one output,
no variables.


*Limitations*

The TF is flexible enough to generate wrappers for many common scientific packages
but the inbuilt automation will not cope with all possible situations. Users can
supply overrides for two tool XML segments - tests and command and the BWA
example in the supplied samples workflow illustrates their use.  

*Installation*

The Docker container is the best way to use the TF because it is preconfigured
to automate new tool testing and has a built in local toolshed where each new tool
is uploaded. It is easy to install without Docker, but you will need to make some 
configuration changes (TODO write a configuration). You can install it most conveniently using the
administrative "Search and browse tool sheds" link. Find the Galaxy Main
toolshed at https://toolshed.g2.bx.psu.edu/ and search for the toolfactory
repository in the Tool Maker section. Open it and review the code and select the option to install it.

Otherwise, if not already there pending an accepted PR,
please add:
<datatype extension="tgz" type="galaxy.datatypes.binary:Binary"
mimetype="multipart/x-gzip" subclass="True" />
to your local data_types_conf.xml.


*Restricted execution*

The tool factory tool itself will then be usable ONLY by admin users -
people with IDs in admin_users. **Yes, that's right. ONLY
admin_users can run this tool** Think about it for a moment. If allowed to
run any arbitrary script on your Galaxy server, the only thing that would
impede a miscreant bent on destroying all your Galaxy data would probably
be lack of appropriate technical skills.

**Generated tool Security**

Once you install a generated tool, it's just
another tool - assuming the script is safe. They just run normally and their
user cannot do anything unusually insecure but please, practice safe toolshed.
Read the code before you install any tool. Especially this one - it is really scary.

**Send Code**

Pull requests and suggestions welcome as git issues please?

**Attribution**

Creating re-usable tools from scripts: The Galaxy Tool Factory
Ross Lazarus; Antony Kaspi; Mark Ziemann; The Galaxy Team
Bioinformatics 2012; doi: 10.1093/bioinformatics/bts573

http://bioinformatics.oxfordjournals.org/cgi/reprint/bts573?ijkey=lczQh1sWrMwdYWJ&keytype=ref

**Licensing**

Copyright Ross Lazarus 2010
ross lazarus at g mail period com

All rights reserved.

Licensed under the LGPL

