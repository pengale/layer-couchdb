import subprocess

from charmhelpers.core.hookenv import open_port, config,
from charmhelpers.fetch import apt_install, add_source, apt_update
from charms.reactive import hook


@hook("install")
def install():
    """
    Install current version of couchdb from package manager.

    # TODO: determine whether it is better to specify the distros for
    which this charm works, or specify a specify version of couch
    here.

    """
    apt_install(['python-software-properties', 'debconf', 'debconf-utils'])
    add_source("ppa:facter-plugins/ppa")
    apt_update()
    apt_install(['couchdb', 'facter', 'facter-customfacts-plugin', 'uuid', 'python-couchdb',
                 'pwgen'])

    # TODO: is this actually the most Charming way to do it?
    DEFAULT_ADMIN_PASSWORD=subprocess.check_output(['pwgen', '-N1']).strip()
    DEFAULT_REPLICATION_PASSWORD=subprocess.check_output(['pwgen', '-N1']).strip()
    
    """
    TODO: convert this facter stuff to some calls to the Python
    ConfigParser, and cut out the facter install stuff above.

    fact-add couchdb_hostname `facter fqdn`
    fact-add couchdb_ip `facter ipaddress`
    fact-add couchdb_port 5984
    fact-add couchdb_replication ${DEFAULT_REPLICATION_PASSWORD}
    fact-add couchdb_admin ${DEFAULT_ADMIN_PASSWORD}

    sed -i.bak -e "s/bind_address =.*/bind_address = `facter couchdb_ip`/" /etc/couchdb/default.ini
    sed -i.bak -e "s/;port =.*/port = `facter couchdb_port`/" \
               -e "s/;bind_address.*/bind_address = `facter couchdb_ip`/" \
               -e "s/; require_valid_user = false/require_valid_user = true/" \
               -e "s/;admin =.*/admin = ${DEFAULT_ADMIN_PASSWORD}/" \
               /etc/couchdb/local.ini
    echo "replication = ${DEFAULT_REPLICATION_PASSWORD}" >> /etc/couchdb/local.ini
    """

    # TODO: maybe make an @when handler that starts when installed,
    # then make a handler that opens port once when both installed and
    # started?
    start()

    # TOOD open-port `facter couchdb_port`/TCP
    # TODO open_port(<put port here>)

@hook("start")
def start():
    """
    Start couch, or, in the case where couch is already running, restart couch.
    """
    if subprocess.call(['service', 'couchdb', 'status']):
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
def db_relation_join():
    """
    TODO: read up about relations work in the reactive work, and write
    appropriate code here.

    """
    # TODO: relation-set host=`facter couchdb_hostname` ip=`facter couchdb_ip`  port=`facter couchdb_port` admin=`facter couchdb_admin`
    # TODO: echo $ENSEMBLE_REMOTE_UNIT joined

