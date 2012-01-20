#!/usr/bin/python
# -*- coding: utf8 -*-

import sys
try:
    import argparse
except ImportError:
    print "Package python-argparse is missing. Please install it."
    sys.exit(1)
import traceback
try:
    import simplejson as json
except ImportError:
    print "Package python-simplejson is missing. Please install it."
    sys.exit(1)
from aptmachine import AptMachine
from helpers import list_print, colorize, leet_equal_signs, print_errors
from helpers import BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE

# load server connection list
config = open('config.json')
servers = json.load(config)

# reference server has to be first one
servers = sorted(servers, key=lambda k: k.get('reference'), reverse=True)

# fancy coloring if in a real shell
color = False
if sys.stdout.isatty():
    color = True

def apt_task(args):
    """ apt-get ... ausführen """
    for server in servers:
        try:
            print colorize(leet_equal_signs(server.get('host')), color and YELLOW)
            apt_cmd = AptMachine(apt_command=args.apt_executable, debug=args.verbose, simulate=args.simulate, **server)
            # process task to apt-get
            print apt_cmd.execute_apt(args.command, args.packages, args.apt_options)
            print colorize('[OK]', color and GREEN)
        except Exception, ex:
            print_errors(ex, color)
        finally:
            try:
                apt_cmd.close()
            except Exception, ex:
                pass

def shell_task(args):
    """ eigene kommandos in der shell ausführen """
    for server in servers:
        try:
            print colorize(leet_equal_signs(server.get('host')), color and YELLOW)
            apt_cmd = AptMachine(debug=args.verbose, **server)
            print apt_cmd._execute(args.shell_command)
            print colorize('[OK]', color and GREEN)
        except Exception, ex:
            print_errors(ex, color)
        finally:
            try:
                apt_cmd.close()
            except Exception, ex:
                pass

def sync_task(args):
    """ Sync bedeutet, die pakete von einem in einen anderen Status zu heben, wenn das vorher auf dem Masterserver auch passiert ist.
        Hier die Liste der möglichen Änderungen:
            install   -> deinstall, purge, hold
            deinstall -> install
            purge     -> install
            hold      -> install
        Im Status "unknown" tun wir nichts... vorerst :)
    """
    master_list = list()
    master_dist = ''
    for server in servers:
        try:
            print colorize(leet_equal_signs(server.get('host')), color and YELLOW)
            apt_cmd = AptMachine(apt_command=args.apt_executable, debug=args.verbose, simulate=args.simulate, **server)
            full_lists = args.full_lists
            package_list = apt_cmd.get_all_packages()
            print 'Operating System:', apt_cmd.distribution
            print 'Packages listed:', len(package_list)
            if server.get('reference'):
                master_dist = apt_cmd.distribution
                print colorize('This server is reference, generating master list.', color and BLUE)
                master_list = package_list
            elif master_list:
                try:
                    print colorize('This server will now be synchronized with the master server.', color and BLUE)
                    if apt_cmd.distribution != master_dist:
                        print colorize("WARNING operating system differs from master server", color and YELLOW)
                    print colorize("[01/16] (missing) unknown => install", color and GREEN)
                    print colorize("[02/16] (missing) unknown => hold", color and GREEN)
                    print colorize("[03/16] (missing) remove => purge", color and GREEN)
                    print colorize("[04/16] (missing) remove => hold", color and GREEN)
                    print colorize("[05/16] (missing) purge => hold", color and GREEN)
                    print colorize("[06/16] (missing) hold => install", color and GREEN)
                    print colorize("[07/16] (missing) hold => remove", color and GREEN)
                    print colorize("[08/16] (missing) hold => purge", color and GREEN)
                    print colorize("[09/16 apt-get update]", color and GREEN)
                    apt_cmd.execute_apt('update')
                    print colorize('[OK]', color and GREEN)
                except Exception, e:
                    print_errors(e, color)

                try:
                    missing_packages = apt_cmd.get_missing_packages(master_list)
                    print colorize("[10/16 remove, purge => install]", color and GREEN), list_print(missing_packages, full_lists)
                    if missing_packages:
                        print apt_cmd.install(missing_packages)
                        print colorize('[OK]', color and GREEN)
                except Exception, e:
                    print_errors(e, color)

                try:
                    redundant_packages = apt_cmd.get_redundant_packages(master_list)
                    print colorize("[11/16 install => remove]", color and GREEN), list_print(redundant_packages, full_lists)
                    if redundant_packages:
                        print apt_cmd.remove(redundant_packages)
                        print colorize('[OK]', color and GREEN)
                except Exception, e:
                    print_errors(e, color)

                try:
                    purged_packages = apt_cmd.get_purged_packages(master_list)
                    print colorize("[12/16 install => purge]", color and GREEN), list_print(purged_packages, full_lists)
                    if purged_packages:
                        print apt_cmd.remove(purged_packages, purge=True)
                        print colorize('[OK]', color and GREEN)
                except Exception, e:
                    print_errors(e, color)

                try:
                    held_packages = apt_cmd.get_hold_packages(master_list)
                    print colorize("[13/16 install => hold]", color and GREEN), list_print(held_packages, full_lists)
                    if held_packages:
                        print apt_cmd.hold(held_packages)
                        print colorize('[OK]', color and GREEN)
                except Exception, e:
                    print_errors(e, color)

                # some cleanup tasks
                try:
                    print colorize("[14/16 autoremove]", color and GREEN)
                    apt_cmd.execute_apt('autoremove')
                    print colorize('[OK]', color and GREEN)
                except Exception, e:
                    print_errors(e, color)
                try:
                    print colorize("[15/16 clean]", color and GREEN)
                    apt_cmd.execute_apt('clean')
                    print colorize('[OK]', color and GREEN)
                except Exception, e:
                    print_errors(e, color)
                try:
                    print colorize("[16/16 autoclean]", color and GREEN)
                    apt_cmd.execute_apt('autoclean')
                    print colorize('[OK]', color and GREEN)
                except Exception, e:
                    print_errors(e, color)
            else:
                print colorize("Sorry, we don't have a master list to synchronize to.", color and BLUE)
        except Exception, ex:
            print_errors(ex, color)
        except KeyboardInterrupt:
            print colorize('Interrupt by user', color and RED)
            try:
                apt_cmd.close()
            except Exception, ex:
                pass
            sys.exit(1)
        finally:
            try:
                apt_cmd.close()
            except Exception, ex:
                pass

# komplettes parsen aller argumente mit subparsern (jeweils für sync, apt-get und command)
parser = argparse.ArgumentParser(description='Yet Another Remote Apt Tool executes remote apt tasks :)')

parser.add_argument('-v', '--verbose', action='store_true', default=False, help='enables verbose debug output')
parser.add_argument('-c', '--color', action='store_true', default=False, help='forces colorized output')
subparsers = parser.add_subparsers(help='"sync", "apt-get" or "command"', metavar='task')

parser_sync = subparsers.add_parser('sync', help='Synchronize your packages between all hosts')
parser_sync.set_defaults(func=sync_task)
parser_sync.add_argument('-o', '--apt-options', nargs='+', default=list(), help='list of options given for apt-get, e.g. -y for aptitude use', metavar='option')
parser_sync.add_argument('-e', '--apt-executable', default='/usr/bin/apt-get', help='specifies another executable for apt, e.g. aptitude (default: %(default)s)', metavar='command')
parser_sync.add_argument('-s', '--simulate', required=False, action='store_true', default=False, help='enables simulate mode, same as -o="-s"')
parser_sync.add_argument('-l', '--full-lists', action='store_false', default=400, help='shows detailed package lists when synchronizing')

parser_apt = subparsers.add_parser('apt-get', help='Executes apt-get commands on all hosts')
parser_apt.set_defaults(func=apt_task)
parser_apt.add_argument('command', choices=['install', 'remove', 'purge', 'update', 'upgrade'], help='apt-get command to execute')
parser_apt.add_argument('packages', nargs='*', default=None, help='package list for install/remove task', metavar='package')
parser_apt.add_argument('-o', '--apt-options', nargs='+', default=list(), help='list of options given for apt-get', metavar='option')
parser_apt.add_argument('-e', '--apt-executable', default='/usr/bin/apt-get', help='specifies another executable for apt, e.g. aptitude (default: %(default)s)', metavar='command')
parser_apt.add_argument('-s', '--simulate', required=False, action='store_true', default=False, help='enables simulate mode, same as -o="-s"')

parser_shell = subparsers.add_parser('command', help='Execute a shell command on all hosts')
parser_shell.set_defaults(func=shell_task)
parser_shell.add_argument('shell_command', help='executes given command at the target host shell')

args = parser.parse_args()
color = color or args.color
args.func(args)
