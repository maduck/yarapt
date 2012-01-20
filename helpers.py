#!/usr/bin/python
# -*- coding: utf8 -*-

# shell color codes
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = [i + 30 for i in range(8)]

def print_errors(ex, color=None):
    """ helper function for less tracebacks """
    error_list = str(ex).split('\n')
    for error in error_list:
        print colorize(error, color and RED)

def list_print(content_list, max_length=False):
    """ helper function which generates a string out of a list
        truncating it after max_length chars if needed """
    if not max_length:
        return ", ".join(content_list)
    tmp = []
    length_count = 0
    for item in content_list:
        length_count += len(item)
        if length_count < max_length:
            tmp.append(item)
        else:
            tmp.append('... (%d more)' % (len(content_list) - len(tmp)))
            break
    return ", ".join(tmp)

def colorize(message, color, bold=True):
    """ helper function which gives us color in a terminal """
    if not color:
        return message
    attr = [str(color)]
    if bold:
        attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), message)

def leet_equal_signs(message, max_length=50):
    """ ===== helper function ===== """
    count = (max_length - len(message) - 2)/2.0
    output = "%s %s %s" % (int(count) * "=", message, int(round(count)) * "=")
    return output
