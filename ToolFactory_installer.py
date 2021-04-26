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
import os
import subprocess
import sys
import tarfile
import time
import lxml.etree as ET


myversion = "V2.2 April 2021"
verbose = True
debug = True
toolFactoryURL = "https://github.com/fubar2/toolfactory"

def timenow():
    """return current time as a string"""
    return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(time.time()))

class ToolConfUpdaterq():
    # update config/tool_conf.xml with a new tool unpacked in /tools
    # requires highly insecure docker settings - like write to tool_conf.xml and to tools !
    # if in a container possibly not so courageous.
    # Fine on your own laptop but security red flag for most production instances

    def __init__(self, args=None):
        self.tool_path = args.tool_path
        self.tool_conf_path = args.tool_conf_path
        self.new_tool_archive_path = args.new_tool_archive_path
        self.new_tool_name = args.new_tool_name
        self.our_name = 'ToolFactory'
        tff = tarfile.open(self.new_tool_archive_path, "r:*")
        flist = tff.getnames()
        ourdir = os.path.commonpath(flist) # eg pyrevpos
        ourxml = [x for x in flist if x.lower().endswith('.xml')]
        res = tff.extractall(self.tool_path)
        self.update_toolconf(ourdir,ourxml)

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
        ourtools = TFsection.findall('tool')
        conf_tools = [x.attrib['file'] for x in our_tools]
        for xml in ourxml:   # may be > 1
            print(xml)
            if not xml in conf_tools: # new - do nothing if already there
                updated = True
                ET.SubElement(TFsection, 'tool', {'file':xml})
        if updated:
            tree.write(self.tool_conf_path, pretty_print=True)

class ToolConfUpdater():
    # update config/tool_conf.xml with a new tool unpacked in /tools
    # requires highly insecure docker settings - like write to tool_conf.xml and to tools !
    # if in a container possibly not so courageous.
    # Fine on your own laptop but security red flag for most production instances

    def __init__(self, tool_path, tool_conf_path, new_tool_archive_path, new_tool_name):
        self.tool_path = tool_path
        self.tool_conf_path = tool_conf_path
        self.new_tool_archive_path = new_tool_archive_path
        self.new_tool_name = new_tool_name
        self.our_name = 'ToolFactory'
        tff = tarfile.open(self.new_tool_archive_path, "r:*")
        flist = tff.getnames()
        ourdir = os.path.commonpath(flist) # eg pyrevpos
        ourxml = [x for x in flist if x.lower().endswith('.xml')]
        res = tff.extractall(self.tool_path)
        self.update_toolconf(ourdir,ourxml)

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
        print(ourxml,'\n',conf_tools)
        for xml in ourxml:   # may be > 1
            print(xml)
            if not xml in conf_tools: # new - do nothing if already there
                updated = True
                ET.SubElement(TFsection, 'tool', {'file':xml})
        ET.indent(tree)
        tree.write(self.tool_conf_path, pretty_print=True)


def main():
    """
    This is a Galaxy wrapper.
    It expects to be called by a special purpose tool.xml

    """
    parser = argparse.ArgumentParser()
    a = parser.add_argument
    a("--new_tool_archive_path", default=None)
    a("--new_tool_name", default=None)
    a("--tool_path", default='/tmp/tooltesting')
    a("--tool_conf_path", default='/tmp/tooltesting/tool_conf.xml')
    a("--galaxy_root", default="/galaxy-central")
    a("--galaxy_venv", default="/galaxy_venv")
    args = parser.parse_args()
    tcu = ToolConfUpdater(args.tool_path, args.tool_conf_path, args.new_tool_archive_path, args.new_tool_name)


if __name__ == "__main__":
    main()
