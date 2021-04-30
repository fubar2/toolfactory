#!/usr/bin/python
from datetime import datetime, timedelta
from io import BytesIO as BIO
import logging
import os
import subprocess
import tarfile
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from watchdog.events import PatternMatchingEventHandler

class ToolHandler(PatternMatchingEventHandler):

    def __init__(self, watchme):
        PatternMatchingEventHandler.__init__(self, patterns=['*.xml'],
                ignore_directories=False, case_sensitive=False)
        self.last_modified = datetime.now()
        self.tool_dir = watchme
        self.work_dir = os.getcwd()
        self.galaxy_root = os.path.split(watchme)[0]
        logging.info(self.galaxy_root)
        self.tar_dir = os.path.join(self.galaxy_root, 'tooltardir')
        if not os.path.exists(self.tar_dir):
                os.mkdir(self.tar_dir)

    def on_created(self, event):
        self.on_modified(event)

    def on_modified(self, event):
        if datetime.now() - self.last_modified < timedelta(seconds=1):
            return
        else:
            if os.path.exists(event.src_path):
                self.last_modified = datetime.now()
                logging.info(f"{event.src_path} was {event.event_type}")
                p = self.planemo_test(event.src_path)
                if p:
                    if p.returncode == 0:
                        newtarpath = self.makeToolTar(event.src_path)
                        logging.info('### Tested toolshed tarball %s written' % newtarpath)
                    else:
                        logging.debug('### planemo stdout:')
                        logging.debug(p.stdout)
                        logging.debug('### planemo stderr:')
                        logging.debug(p.stderr)
                        logging.info('### Planemo call return code =' % p.returncode)
            else:
                logging.info('Directory %s deleted' % event.src_path)

    def planemo_test(self, xml_path):
        toolpath, toolfile = os.path.split(xml_path)
        dirlist = os.listdir(toolpath)
        toolname = os.path.basename(toolpath)
        logging.info('### test dirlist %s, path %s toolname %s' % (dirlist, xml_path, toolname))
        xmls = [x for x in dirlist if os.path.splitext(x)[1] == '.xml']
        if not len(xmls) > 0:
            logging.warning('Found no xml files after change to %s' % xml_path)
            return None
        tool_test_output = os.path.join(toolpath, f"{toolname}_planemo_test_report.html")
        cll = [
            "planemo",
            "test",
            "--test_output",
            tool_test_output,
            "--galaxy_root",
            self.galaxy_root,
            "--update_test_data",
            xml_path,
        ]
        logging.info('### calling %s' % ' '.join(cll))
        p = subprocess.run(
            cll,
            cwd = toolpath,
            shell=False,
            capture_output=True,
            encoding='utf8',
        )
        return p

    def makeToolTar(self, xml_path):
        """move outputs into test-data and prepare the tarball"""
        excludeme = "_planemo_test_report.html"

        def exclude_function(tarinfo):
            filename = tarinfo.name
            return None if filename.endswith(excludeme) else tarinfo

        tooldir, xml_file = os.path.split(xml_path)
        os.chdir(self.tool_dir)
        toolname = os.path.splitext(xml_file)[0]
        newtarpath = os.path.join(self.tar_dir, '%s_toolshed.gz' % toolname)
        tf = tarfile.open(newtarpath, "w:gz")
        tf.add(
            name=toolname,
            arcname=toolname,
            filter=exclude_function,
        )
        tf.close()
        os.chdir(self.work_dir)
        return newtarpath


if __name__ == "__main__":
    watchme = '/home/ross/gal21/tools'
    logging.basicConfig(level=logging.INFO,
                    #filename = os.path.join(watchme,"toolwatcher.log")
                    #filemode = "w",
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
    event_handler = ToolHandler(watchme=watchme)
    observer = Observer()
    observer.schedule(event_handler, path=watchme, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()



