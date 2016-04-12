import codecs
import configparser
import shutil
import subprocess
from shutil import copyfile

from charmhelpers.core.hookenv import open_port, config, relation_set, relation_get
from charmhelpers.fetch import apt_install, add_source, apt_update
from charms.leadership import leader_set, leader_get
from charms.reactive import hook, when, not_unless

#
# Helpers
#

def _write_config(config_path, name, entries):
    """
    Write out a given config to a file.

    @param str config_path: Directory containing configs.
    @param str name: Name of the config file (leave out the .ini part)
    @param list entries: A dict of entries to write to the config, in the following format:
                         { "section": <section_name>, "key": <key name>, "value": <value> }
                         (Note that all values in the dict must be strings.)

    """
    parser = configparser.ConfigParser()
    file_path = '{}/{}.ini'.format(config_path, name)

    # Backup the existing config.
    shutil.copyfile(file_path, '{}.bak'.format(file_path))

    # Read it.
    with codecs.open(file_path, 'r', 'utf8') as conf_file:
        parser.read_file(conf_file)

    # Modify it.
    for entry in entries:
        if not parser.has_section(entry['section']):
            parser.add_section(entry['section'])

    parser.set(entry['section'], entry['key'], entry['value'])

    # Write it out.
    with open(file_path, 'w') as conf_file:
        parser.write(conf_file)

    # TODO: tell configparser to stop clobbering the comments in the
    # original file.

def _write_couch_configs(config_path='/etc/couchdb'):
    """
    Edit the default couch config files.

    @param str config_path: The full path to the directory where the files are stored in
                            the system. Most of the time, the default will be fine.

    """

    COUCH_CONFIGS = [
        { 'name': 'local', 'entries': [
            { 'section': 'httpd', 'key': 'bind_address', 'value': config('couchdb-bind-addr') },
            { 'section': 'httpd', 'key': 'port', 'value': str(config('couchdb-port')) },
        ]},
        { 'name': 'default', 'entries': [
            { 'section': 'httpd', 'key': 'bind_address', 'value': config('couchdb-bind-addr') },
        ]},
    ]

    for conf in COUCH_CONFIGS:
        _write_config(config_path, conf['name'], conf['entries'])

#
# Handlers
#

@when("leader-elected")
def maybe_generate_passwords():
    """
    If we're the leader, and we haven't generated passwords yet, generate them.

    @param string name: The name of the key that will store the password.

    """
    if not leader_get('passwords'):
        admin_pass = subprocess.check_output(['pwgen', '-N1']).strip().decode('utf-8')
        repl_pass = subprocess.check_output(['pwgen', '-N1']).strip().decode('utf-8')
        leader_set(passwords={"admin_pass": admin_pass, "repl_pass": repl_pass})


@when("leader-settings-changed")
def end_admin_party(config_path='/etc/couchdb'):
    """
    Couch starts out in "admin party" mode, which means that anyone
    can create and edit databases. Once it looks like the leader has
    generated some passwords, write them out to disk.

    @param str config_path: The location of the config files in the system.

    # TODO: this is not getting triggered. Not sure whether it's an
    # issue with this hook, with the 'maybe_generate_passwords' hook
    # above, or with my understanding of how the leadership automagic
    # works in general.

    """
    passwords = leader_get('passwords')

    if not passwords:
        return

    entries = [
        { 'section': 'admins', 'key': 'admin', 'value': passwords['admin_pass'] },
        { 'section': 'admins', 'key': 'replication', 'value': passwords['repl_pass'] },
        { 'section': 'couch_httpd_auth', 'key': 'require_valid_user', 'value': 'true' },
        # TODO: get rid of the following section? It's mainly for manual testing, and
        # it does not fit in with couch's security model.
        { 'section': 'juju_notes', 'key': 'admin_pass', 'value': passwords['admin_pass'] },
        { 'section': 'juju_notes', 'key': 'repl_pass', 'value': passwords['repl_pass'] },
    ]
    _write_config(config_path, "local", entries)

    start()  # TODO: trigger start with a @when hook


@hook('install')
def install():
    """
    Install the current version of couchdb from package manager.

    Start it up once installed. Defer ending the admin party -- we'll
    handle it elsewhere.

    """
    # Install packages
    # TODO: audit these packages. I don't think that all of them are necessary.
    apt_install(['python-software-properties', 'debconf', 'debconf-utils', 'couchdb',
                 'uuid', 'python-couchdb', 'pwgen'])

    # Edit config files
    _write_couch_configs()

    # Start couch
    start()  # TODO: trigger with an @when hook

    # Open the couch port
    open_port(config('couchdb-port'))


@hook('start')
def start():
    """
    Start couch, or, in the case where couch is already running, restart couch.

    """
    if not subprocess.call(['service', 'couchdb', 'status']):  # 'not' because 0 means 'a-okay'
        subprocess.check_call(['service', 'couchdb', 'restart'])
    else:
        subprocess.check_call(['service', 'couchdb', 'start'])


@hook('stop')
def stop():
    """
    Halt couch.

    """
    subprocess.check_call(['service', 'couchdb', 'stop'])


@hook('db-relation-joined')
def db_relation_joined():
    """
    Hook to run when somebody connects to us.

    """

    passwords = leader_get("passwords")

    # TODO: figure out how to get the right values for couchdb-host and couchdb-ip.
    relation_set(
        host=config('couchdb-host'),
        ip=config('couchdb-ip'),
        port=config('couchdb-port'),
        admin_pass=passwords['admin_pass'],
        repl_pass=passwords['repl_pass']
    )

    # TODO: Figure out what this was meant to do, and convert to more purely Python equivalent.
    subprocess.check_call([
        'echo',
        '$ENSEMBLE_REMOTE_UNIT',
        'joined'
    ])
