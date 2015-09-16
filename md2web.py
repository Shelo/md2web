import os, time, sys, paramiko, markdown, codecs
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from scp import SCPClient
from markdown.extensions.wikilinks import WikiLinkExtension
from configs import parse_configs
from getpass import getpass


class Watcher(PatternMatchingEventHandler):
    patterns = ['*.md']

    def __init__(self, file_to_watch, dest_path):
        PatternMatchingEventHandler.__init__(self)

        self.file_to_watch = file_to_watch
        self.dest_path = dest_path

        if os.path.isdir(self.file_to_watch):
            self.file_to_watch = None

        self.default_template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
            "template.html")

        self.ssh_client = create_ssh_client(*get_configs())
        self.scp = SCPClient(self.ssh_client.get_transport())

        if self.file_to_watch != None:
            self.fire(self.file_to_watch)
        else:
            mds = [filename for filename in os.listdir(".") if filename.endswith(".md")]
            for md in mds:
                self.fire(md)

        print "Initialization completed. Listening for changes..."

    def process(self, event):
        base_name = os.path.basename(event.src_path)
        if self.file_to_watch == None or os.path.basename(event.src_path) == self.file_to_watch:
            if event.event_type in ["modified", "created"]:
                self.fire(event.src_path)

    def fire(self, path):
        print "[" + os.path.basename(path) + "] Converting...",
        try:
            # try to convert the file, this will prevent the demon to fall if the converter give
            # us some error, allowing the user to fix it.
            file_name = self.convert(path)
        except Exception:
            # in the case of some exception, notify the user and quit trying.
            print "Error while converting to html."
            return

        # after the successful convertion, send the file to the SSH server.
        print "Sending...",
        if self.file_to_watch != None:
            # in case we watch just one file.
            self.scp.put(file_name, self.dest_path)
        else:
            # in case we are watching a directory.
            self.scp.put(file_name, os.path.join(self.dest_path, os.path.basename(file_name).replace(".md", "")))

        # finally, remove the temp and notify the sucess.
        print "File sent.",
        os.remove(path + ".html")
        print "Temp removed. Done."

    def convert(self, file_to_convert):
        # read the file and add the content table.
        source_file = codecs.open(file_to_convert, mode="r", encoding="utf-8")
        text = "[TOC]\n" + source_file.read()
        source_file.close()

        # convert it to html with the extensions given, this could raise an exception, but this
        # method is supposed to live inside a try / except.
        html = markdown.markdown(text, encoding="utf-8", extensions=[WikiLinkExtension(end_url='.html', base_url=""), 'markdown.extensions.tables', 'markdown.extensions.toc', 'markdown.extensions.nl2br'])

        # try to find a "template.html" in the working directory, if we can't find one, use the one
        # packed with this program.
        if os.path.isfile("template.html"):
            # template defined by the user.
            template_path = "template.html"
        else:
            # default template.
            template_path = self.default_template_path

        # read the template file.
        template_file = codecs.open(template_path, mode="r", encoding="utf-8")
        template = template_file.read()
        template_file.close()

        # this is the name of the temp file.
        file_target_name = file_to_convert + ".html"

        # get the base name to work as the title of the temp file, write the html in it with the
        # title and content and finish.
        base_name = os.path.basename(os.path.splitext(file_to_convert)[0])
        write_file = codecs.open(file_target_name, "w", encoding="utf-8",
                errors="xmlcharrefreplace")
        write_file.write(template % (base_name, html))
        write_file.close()

        return file_target_name

    def on_modified(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)

def get_configs():
    configs = []
    if os.path.isfile("configs.cfg"):
        options = parse_configs("configs.cfg")

        if "server" in options and "port" in options and "user" in options:
            configs.append(options["server"])
            configs.append(int(options["port"]))
            configs.append(options["user"])
            configs.append(getpass())

        else:
            print "Configuration file missing options."
            exit(1)

    else:
        configs.append(raw_input("Server: "))
        configs.append(int(raw_input("Port: ")))
        configs.append(raw_input("User: "))
        configs.append(getpass())

    return tuple(configs)

def valid_argv():
    if len(sys.argv) != 3:
        return False

    if not os.path.isfile(sys.argv[1]):
        if not os.path.isdir(sys.argv[1]):
            return False
        else:
            return True

    return True


def watch(base_path, file_to_watch, dest_path):
    observer = Observer()
    observer.schedule(Watcher(file_to_watch, dest_path), path=base_path)
    observer.start()

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


def main():
    if not valid_argv():
        return False, "Invalid file argument or file dest."

    file_to_watch = sys.argv[1]
    dest_path = sys.argv[2]
    base_path = os.getcwd()

    watch(base_path, file_to_watch, dest_path)

    return True, "Watcher closed."


def create_ssh_client(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client


if __name__ == '__main__':
    exit_status, message = main()

    if not exit_status:
        print message
