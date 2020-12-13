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

