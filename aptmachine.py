#!/usr/bin/python
# -*- coding: utf8 -*-
import ssh
import logging
import os
import sys
import time
import signal
from subprocess import Popen, PIPE

class YaraptException(Exception):
    pass
class ShellException(YaraptException):
    pass
class SSHException(YaraptException):
    pass
class TimeoutException(YaraptException):
    pass
class LogException(YaraptException):
    pass

class AptMachine():
    """ class for doing various apt related tasks """
    connection = None
    sudo = False
    host = None
    simulate = False
    debug = False
    apt_executable = '/usr/bin/apt-get'
    distribution = ''

    def __init__(self, **kwargs):
        """ baut eine verbindung auf, wahlweise per ssh oder lokal """
        # initiate logging
        log_level = logging.WARNING
        self.host = kwargs.get('host')
        self.simulate = kwargs.get('simulate')
        self.apt_executable = kwargs.get('apt_command', self.apt_executable)
        self.debug = kwargs.get('debug', False)
        if self.debug:
            log_level = logging.DEBUG
        try:
            log_file = './var/log/yarapt.log'
            logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s %(message)s', filename=log_file)
        except IOError, (errno, strerror):
            raise LogException("Fatal %r: %s (Error #%s)" % (log_file, strerror, errno))

        self.sudo = kwargs.get('sudo', False)

        # initiate ssh if needed
        if kwargs.get('ssh'):
            logging.info('Connecting to ssh://%s' % self.host)
            try:
                self.connection = ssh.Connection(self.host, username=kwargs['username'], password=kwargs.get('password'), private_key=kwargs.get('private_key'), level=log_level)
            except Exception, ex:
                logging.error('Could not connect to %s@%s: %s' % (kwargs['username'], self.host, ex))
                raise SSHException('Could not connect to %s@%s: %s' % (kwargs['username'], self.host, ex))
        try:
            self.distribution = self._execute('/usr/bin/lsb_release -ds')
        except Exception:
            pass

    def _execute_local(self, command, timeout=60):
        proc = Popen(command, shell=True, stdout=PIPE, stderr=PIPE, stdin=PIPE)
        # poll for terminated status till timeout is reached
        start_time = time.time()
        duration = 0
        while True:
            if proc.poll() is not None:
                break
            duration = time.time() - start_time
            if timeout and duration > timeout:
                os.kill(proc.pid, signal.SIGKILL)
                raise TimeoutException('Command "%s" on host %s timed out after %d seconds.\n%s' % (command, self.host, timeout, proc.stdout.read().strip()))
                break
            time.sleep(0.1)
        stdout, stderr = proc.communicate()
        returncode = proc.returncode
        if returncode > 0:
            raise ShellException('Command "%s" on host %s returned %d, messages:\n%s' % (command, self.host, returncode, stderr.strip()))
        if stderr:
            logging.warn('Got error output for command %r on host %s:\n %s' % (command, self.host, stderr.strip()))
        return stdout.strip()

    def _execute_ssh(self, command, timeout=15):
        stdout, stderr = self.connection.execute(command, timeout)
        if stdout:
            stdout = stdout.strip()
        if stderr:
            stderr = stderr.strip()
        returncode = self.connection.returncode
        if returncode is None:
            raise TimeoutException('Command "%s" on host %s timed out after %d seconds.\n%s' % (command, self.host, timeout, stdout))
        if returncode > 0:
            raise ShellException('Command "%s" on host %s returned %d, messages:\n%s' % (command, self.host, returncode, stderr))
        if stderr:
            logging.warn('Got error output for command %r on host %s:\n %s' % (command, self.host, stderr.strip()))
        output = stdout.strip()
        return output

    def _execute(self, command):
        """ führt einen beliebigen befehl aus, wahlweise per ssh oder lokal """
        command = command.strip()
        if self.connection:
            if self.sudo:
                command = 'sudo %s' % command
            if self.debug:
                print '[DEBUG] Executing ssh command %r' % command
            logging.info('Executing ssh command %r' % command)
            return self._execute_ssh(command)
        else:
            if self.sudo:
                command = 'sudo "%s"' % command
            if self.debug:
                print '[DEBUG] Executing local command %r' % command
            logging.info('Executing local command %r' % command)
            return self._execute_local(command)

    def execute_apt(self, command, params=list(), options=list()):
        """ führt einen bestimmten apt-befehl aus, wahlweise per ssh oder lokal """
        # diese kommandos brauchen dringend parameter.
        my_options = list(options)
        if self.simulate:
            my_options.append('-s')

        shell_command = '%s %s %s %s' % (
            self.apt_executable,
            ' '.join(my_options),
            command,
            ' '.join(params)
        )
        output = self._execute(shell_command)
        return output

    def get_all_packages(self):
        """ listet alle pakete von einem rechner auf"""
        command = "/usr/bin/dpkg --get-selections | /usr/bin/awk '{print $1, $2};'"
        logging.debug('Executing command %s' % command)
        packages = self._execute(command)
        self.package_list = [i.split(' ') for i in packages.split('\n')]
        # remove empty last entry line
        self.package_list.pop()
        return self.package_list

    def _list_to_set_with_filter(self, package_list, package_filter, negate=False):
        tmp = list()
        for package in package_list:
            if len(package) == 2:
                if negate and package[1] != package_filter:
                    tmp.append(package[0])
                if not negate and package[1] == package_filter:
                    tmp.append(package[0])
            else:
                logging.info('Error with package %s' % package)
        return set(tmp)

    def get_missing_packages(self, master_package_list):
        own_pkg = self._list_to_set_with_filter(self.package_list, 'install')
        ref_pkg = self._list_to_set_with_filter(master_package_list, 'install')
        missing = ref_pkg.difference(own_pkg)
        return list(missing)

    def get_redundant_packages(self, master_package_list):
        own_inst_pkg = self._list_to_set_with_filter(self.package_list, 'install')
        own_pkg = self._list_to_set_with_filter(self.package_list, 'deinstall')
        ref_pkg = self._list_to_set_with_filter(master_package_list, 'deinstall')
        missing = ref_pkg.difference(own_pkg).intersection(own_inst_pkg)
        return list(missing)

    def get_purged_packages(self, master_package_list):
        own_inst_pkg = self._list_to_set_with_filter(self.package_list, 'install')
        own_pkg = self._list_to_set_with_filter(self.package_list, 'purge')
        ref_pkg = self._list_to_set_with_filter(master_package_list, 'purge')
        purged = ref_pkg.difference(own_pkg).intersection(own_inst_pkg)
        return list(purged)

    def get_hold_packages(self, master_package_list):
        own_hold_pkg = self._list_to_set_with_filter(self.package_list, 'hold')
        #own_not_hold_pkg = self._list_to_set_with_filter(self.package_list, 'hold', negate=True)
        ref_pkg = self._list_to_set_with_filter(master_package_list, 'hold')
        hold = ref_pkg.difference(own_hold_pkg)
        return list(hold)

    def install(self, package_list):
        """ installiert alle pakete aus package_list """
        output = self.execute_apt("install", package_list)
        logging.debug(repr(output))
        return output

    def remove(self, package_list, purge=False):
        """ entfernt überflüssige pakete """
        command = 'purge' if purge else 'remove'
        logging.debug('executing %r' % command)
        output = self.execute_apt(command, package_list)
        logging.debug(repr(output))
        return output

    def hold(self, package_list):
        command = "aptitude hold %s" % " ".join(package_list)
        logging.debug('executing %r' % command)
        output = self._execute(command)
        return output

    def close(self):
        """ schließt ggfs. die ssh verbindung zum entfernten rechner """
        if self.connection:
            self.connection.close()

    def __del__(self):
        """ für den eiligen benutzer, falls close() nicht explizit aufgerufen wurde. """
        self.close()
