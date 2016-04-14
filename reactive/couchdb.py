"""
Reactive handlers for our CouchDB Charm.

"""

import codecs
import configparser
import json
import shutil
import subprocess

from charmhelpers.core.hookenv import open_port, config, log, DEBUG, WARNING, INFO
from charmhelpers.fetch import apt_install
from charms.leadership import leader_set, leader_get
from charms.reactive import hook, when, when_any, set_state, remove_state, is_state, when_all

#
# Helpers
#

def _write_config(config_path, name, entries):
    """
    Write out a given config to a file.

    @param str config_path: Directory containing configs.
    @param str name: Name of the config file (leave out the .ini part)
    @param list entries: A dict of entries to write to the config, in the following format:
                         {'section': <section_name>, 'key': <key name>, 'value': <value>}
                         (Note that all values in the dict must be strings.)

    """
    log("Writing {}/{}.ini".format(config_path, name), DEBUG)
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

    set_state('couchdb.config_updated')  # Trigger restart

def _write_couch_configs(config_path='/etc/couchdb'):
    """
    Edit the default couch config files.

    @param str config_path: The full path to the directory where the files are stored in
                            the system. Most of the time, the default will be fine.

    """

    COUCH_CONFIGS = [
        {'name': 'local', 'entries': [
            {'section': 'httpd', 'key': 'bind_address', 'value': config('couchdb-bind-addr')},
            {'section': 'httpd', 'key': 'port', 'value': str(config('couchdb-port'))},
        ]},
        {'name': 'default', 'entries': [
            {'section': 'httpd', 'key': 'bind_address', 'value': config('couchdb-bind-addr')},
        ]},
    ]

    for conf in COUCH_CONFIGS:
        _write_config(config_path, conf['name'], conf['entries'])


def _maybe_generate_passwords():
    """
    If the leader hasn't generated passwords yet, generate them.

    """
    if not leader_get('passwords'):
        admin_pass = subprocess.check_output(['pwgen', '-N1']).strip().decode('utf-8')
        repl_pass = subprocess.check_output(['pwgen', '-N1']).strip().decode('utf-8')
        leader_set(passwords=json.dumps({'admin_pass': admin_pass, 'repl_pass': repl_pass}))


#
# Handlers
#

@when_all('couchdb.installed', 'couchdb.admin_party')
def end_admin_party(config_path='/etc/couchdb'):
    """
    Couch starts out in 'admin party' mode, which means that anyone
    can create and edit databases. This routine secures couch, and
    flags us to restart.

    @param str config_path: The location of the config files in the system.

    """
    log("Ending the admin party.", DEBUG)
    _maybe_generate_passwords()

    passwords = json.loads(leader_get('passwords'))

    entries = [
        {'section': 'admins', 'key': 'admin', 'value': passwords['admin_pass']},
        {'section': 'admins', 'key': 'replication', 'value': passwords['repl_pass']},
        {'section': 'couch_httpd_auth', 'key': 'require_valid_user', 'value': 'true'},
        # TODO: get rid of the following section? It's mainly for manual testing, and
        # it does not fit in with couch's security model.
        {'section': 'juju_notes', 'key': 'admin_pass', 'value': passwords['admin_pass']},
        {'section': 'juju_notes', 'key': 'repl_pass', 'value': passwords['repl_pass']},
    ]
    _write_config(config_path, 'local', entries)

    remove_state('couchdb.admin_party')


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
    _write_couch_configs()  # Will set couchdb.config_updated, which should trigger a start.

    log("Installing couch.")

    set_state('couchdb.installed')
    set_state('couchdb.admin_party')

@hook('start')
def start_hook():
    start()

@when_all('couchdb.installed', 'couchdb.config_updated')
def start():
    """
    Start couch, or, in the case where couch is already running, restart couch.

    """
    log("Starting/Restarting CouchDB", DEBUG)
    subprocess.check_call(['service', 'couchdb', 'restart'])

    # Remove the 'config_updated' flag, if any
    if is_state('couchdb.config_updated'):
        remove_state('couchdb.config_updated')

    open_port(config('couchdb-port'))

    set_state('couchdb.started')

@hook('stop')
def stop():
    """
    Halt couch.

    """
    subprocess.check_call(['service', 'couchdb', 'stop'])
    remove_state('couchdb.running')


@hook('db-relation-joined')
def db_relation_joined():
    """
    Hook to run when somebody connects to us.

    """

    passwords = json.loads(leader_get('passwords'))  # TODO: Exception handling.

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
