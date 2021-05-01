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
        self.mininterval = 5
        self.tool_dir = watchme
        self.work_dir = os.getcwd()
        wpath = watchme.split(os.path.sep)
        wpath = [x for x in wpath if x > '']
        self.galaxy_root = os.path.sep.join(wpath[:-1])
        self.galaxy_root = '/%s' % self.galaxy_root
        logging.info(self.galaxy_root)
        self.tar_dir = os.path.join(self.galaxy_root, 'tooltardir')
        if not os.path.exists(self.tar_dir):
                os.mkdir(self.tar_dir)
        self.dir_lastmod = {}

    def dispatch(self,event):
        if os.path.exists(event.src_path):
            lastmod = self.dir_lastmod.get(event.src_path,None):
            self.dir_lastmod[event.src_path] = datetime.now()
            if datetime.now() - lastmod < timedelta(seconds=self.mininterval):
                logging.info('Event %s on %s ignored as less than %d seconds since last event' % (event.event_type,self.mininterval, event.src_path))
                return
            else:
                logging.info(f"{event.src_path} was {event.event_type}")
                if event.event_type in ['modified','created']:
                    toolspath, toolname = os.path.split(event.src_path)
                    dirlist = os.listdir(event.src_path)
                    logging.info('### test dirlist %s, path %s toolname %s' % (dirlist, toolspath, toolname))
                    xmls = [x for x in dirlist if os.path.splitext(x)[1] == '.xml']
                    if not len(xmls) > 0:
                        logging.warning('Found no xml files after change to %s' % event.src_path)
                        return None
                    testflag = os.path.join(event.src_path,'.testme')
                    run_test = os.path.exists(testflag)
                    if run_test:
                        os.remove(testflag):
                        self.dir_lastmod[event.src_path] = datetime.now()
                    p = self.planemo_test(event.src_path, toolname)
                    if p:
                        if p.returncode == 0:
                            newtarpath = self.makeToolTar(event.src_path)
                            logging.info('### Tested toolshed tarball %s written' % newtarpath)
                        else:
                            logging.debug('### planemo stdout:')
                            logging.debug(p.stdout)
                            logging.debug('### planemo stderr:')
                            logging.debug(p.stderr)
                            logging.info('### Planemo call return code = %d' % p.returncode)
                else:
                    logging.info('Event %s on %s ignored' % (event.event_type,event.src_path))


    def planemo_test(self, esp, toolname):
        tool_test_output = os.path.join(esp, f"{toolname}_planemo_test_report.html")
        cll = [
            "planemo",
            "test",
            "--test_output",
            tool_test_output,
            "--update_test_data",
            os.path.join(esp,'%s.xml' % toolname)
        ]
        logging.info('### calling %s' % ' '.join(cll))
        p = subprocess.run(
            cll,
            cwd = esp,
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
    watchme = '/export/galaxy/tools/'
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



