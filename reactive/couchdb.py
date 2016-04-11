from shutil import copyfile
import codecs
import configparser
import shutil
import subprocess

from charmhelpers.core.hookenv import open_port, config
from charmhelpers.fetch import apt_install, add_source, apt_update
from charms.reactive import hook, when


def _set_couch_config(config_path="/etc/couchdb"):
    """
    Edit the default couch config files.

    @param string config_path: The full path to the directory where the files are stored in
                               the system. Most of the time, the default will be fine.

    """

    # Generate values to slot into couch config files
    ADMIN_PASS = subprocess.check_output(['pwgen', '-N1']).strip().decode('utf-8')
    REPL_PASS = subprocess.check_output(['pwgen', '-N1']).strip().decode('utf-8')
    # TODO: Is there a more "Charming" way of generating passwords?
    COUCH_CONFIGS = [
        { "name": "local", "entries": [
            { "section": "httpd", "key": "bind_address", "value": config("couchdb-bind-addr") },
            { "section": "httpd", "key": "port", "value": str(config("couchdb-port")) },
            { "section": "couch_httpd_auth", "key": "require_valid_user", "value": "true" },
            { "section": "admins", "key": "admin", "value": ADMIN_PASS },
            { "section": "admins", "key": "replication", "value": REPL_PASS },
        ]},
        { "name": "default", "entries": [
            { "section": "httpd", "key": "bind_address", "value": config("couchdb-bind-addr") },
        ]},
        { "name": "juju_generated", "entries": [
            { "section": "creds", "key": "admin_pass", "value": ADMIN_PASS },
            { "section": "creds", "key": "repl_pass", "value": REPL_PASS },
        ]}
    ]

    # Write out the config we've generated above.
    # TODO: tell configparser to stop clobbering the comments in the
    # original local.ini and default.ini files.
    for conf in COUCH_CONFIGS:
        parser = configparser.ConfigParser()
        file_path = "{}/{}.ini".format(config_path, conf['name'])
        try:
            parser.read_file(codecs.open(file_path, "r", "utf8"))
            shutil.copyfile(file_path, "{}.bak".format(file_path))  # Backups are good.
        except(FileNotFoundError):
            # If the file doesn't exist, that's okay. We'll create it below.
            # TODO: we should probably raise if default.ini doesn't exist.
            pass
        for entry in conf["entries"]:
            if not parser.has_section(entry["section"]):
                parser.add_section(entry["section"])

            parser.set(entry["section"], entry["key"], entry["value"])

        with open(file_path, "w") as conf_file:
            parser.write(conf_file)

    # TODO: change the permissions on the juju_generated file, so that
    # only root can read it.
    # TODO: ... or better yet, store it in the leadership settings (see Postgresql charm)


@hook("install")
def install():
    """
    Install current version of couchdb from package manager.

    # TODO: determine whether it is better to specify the distros for
    which this charm works, or specify a specify version of couch
    here.

    """
    # TODO: audit these packages. I don't think that all of them are necessary.
    # Install packages
    apt_install(['python-software-properties', 'debconf', 'debconf-utils'])
    apt_update()
    apt_install(['couchdb', 'uuid', 'python-couchdb', 'pwgen'])

    # Edit config files
    _set_couch_config()

    # Start couch
    # TODO: Move this to a @when handler? (or just add an @when to start)
    start()

    # Open the couch port
    # TODO: Move this to @when handler?
    open_port(config("couchdb-port"))


@hook("start")
def start():
    """
    Start couch, or, in the case where couch is already running, restart couch.
    """
    if not subprocess.call(['service', 'couchdb', 'status']):  # 'not' because 0 means 'a-okay'
        subprocess.check_call(['service', 'couchdb', 'restart'])
    else:
        subprocess.check_call(['service', 'couchdb', 'start'])


@hook("stop")
def stop():
    """
    Halt couch.
    """
    subprocess.check_call(['service', 'couchdb', 'stop'])


@hook("db-relation-joined")
def db_relation_joined():
    """
    # TODO: Actually convert this into Python.
    # TODO: figure out how to get the right values for couchdb-host and couchdb-ip.
    """
    subprocess.check_call([
        'relation-set',
        "host={}".format(config("couchdb-host")),
        "ip={}".format(config("couchdb-ip")),
        "port={}".format(config("couchdb-port"))
    ])
    subprocess.check_call([
        "echo",
        "$ENSEMBLE_REMOTE_UNIT",
        "joined"
    ])
