#!/usr/bin/python
# -*- coding: utf8 -*-
"""Friendly Python SSH2 interface."""

import os
import sys
import logging
import getpass
import time
try:
    import paramiko
except ImportError:
    print "Package python-paramiko is missing. Please install it."
    sys.exit(1)

from socket import timeout

class Connection(object):
    """Connects and logs into the specified hostname. 
    Arguments that are not given are guessed from the environment."""

    def __init__(self, host, username=None, private_key=None, password=None, port=22, level=logging.DEBUG):
        self._sftp_live = False
        self._sftp = None
        if not username:
            username = os.environ['LOGNAME']

        paramiko.util.log_to_file('/dev/null', level=level)

        # Begin the SSH transport.
        self._transport = paramiko.Transport((host, port))
        self._tranport_live = True
        # Authenticate the transport.
        if password:
            # Using Password.
            self._transport.connect(username=username, password=password)
        else:
            # Use Private Key.
            if not private_key:
                # Try to use default key.
                if os.path.exists(os.path.expanduser('~/.ssh/id_rsa')):
                    private_key = '~/.ssh/id_rsa'
                elif os.path.exists(os.path.expanduser('~/.ssh/id_dsa')):
                    private_key = '~/.ssh/id_dsa'
                else:
                    raise TypeError, "You have not specified a password or key."

            private_key_file = os.path.expanduser(private_key)
            try:
                rsa_key = paramiko.RSAKey.from_private_key_file(private_key_file)
            except paramiko.PasswordRequiredException:
                password = getpass.getpass('RSA key password: ')
                rsa_key = paramiko.RSAKey.from_private_key_file(private_key_file, password)
            self._transport.connect(username=username, pkey=rsa_key)

    def _sftp_connect(self):
        """Establish the SFTP connection."""
        if not self._sftp_live:
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
            self._sftp_live = True

    def get(self, remotepath, localpath=None):
        """Copies a file between the remote host and the local host."""
        if not localpath:
            localpath = os.path.split(remotepath)[1]
        self._sftp_connect()
        self._sftp.get(remotepath, localpath)

    def put(self, localpath, remotepath=None):
        """Copies a file between the local host and the remote host."""
        if not remotepath:
            remotepath = os.path.split(localpath)[1]
        self._sftp_connect()
        self._sftp.put(localpath, remotepath)

    def execute(self, command, timeout=10):
        """Execute the given commands on a remote machine."""
        channel = self._transport.open_session()
        channel.setblocking(0)
        channel.set_combine_stderr(False)
        channel.settimeout(0)
        #channel.invoke_shell()
        output = ''
        stderr = ''
        channel.exec_command(command)
        #channel.send(command + '\n')
        duration = 0
        start_time = time.time()

        self.returncode = None
        while not channel.exit_status_ready():
            duration = time.time() - start_time
            if timeout and duration > timeout:
                break
            time.sleep(0.1)

        while channel.recv_stderr_ready():
            stderr += channel.recv_stderr(1024)
        while channel.recv_ready():
            output += channel.recv(1024)

        #import pdb
        #pdb.set_trace()
        if channel.exit_status_ready():
            self.returncode = channel.recv_exit_status()
        channel.close()
        return output, stderr

    def close(self):
        """Closes the connection and cleans up."""
        # Close SFTP Connection.
        if self._sftp_live:
            self._sftp.close()
            self._sftp_live = False
        # Close the SSH Transport.
        if self._tranport_live:
            self._transport.close()
            self._tranport_live = False

    def __del__(self):
        """Attempt to clean up if not explicitly closed."""
        self.close()

def main():
    """Little test when called directly."""
    # Set these to your own details.
    myssh = Connection('example.com')
    myssh.put('ssh.py')
    myssh.close()

# start the ball rolling.
if __name__ == "__main__":
    main()
