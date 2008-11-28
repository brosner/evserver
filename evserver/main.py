#!/usr/bin/python
# Asynchronous Wsgi Server  (based on Christopher Stawarz proposal)
#
# references:
#  http://python.org/dev/peps/pep-0333/#the-start-response-callable
#  v3 http://www.mail-archive.com/web-sig@python.org/msg02315.html
#     (beware of the example. dns resolution in curl is not asynchronous)
#  v2 http://www.mail-archive.com/web-sig@python.org/msg02299.html
#  v1 http://www.mail-archive.com/web-sig@python.org/msg02277.html
#

import sys
import os
import logging
import optparse
import ctypes, ctypes.util
import time
import datetime
import platform
from pkg_resources import resource_filename


log = logging.getLogger(os.path.basename(__file__))

FORMAT_FILE = '%(asctime)s %(name)s[%(process)d] %(levelname)10s %(message)s'
FORMAT_CONS = '%(asctime)s %(name)-12s %(levelname)8s\t%(message)s'


if platform.system() == 'Linux':
    libeventbin = 'libevent.so'
elif platform.system() == 'Darwin':
    libeventbin = 'libevent.dylib'
else:
    raise NotImplemented('Unknown platform')


def wsgi_django():
    import django.core.handlers.wsgi as django_wsgi
    from django.conf import settings
    log.info("Running Django. DJANGO_SETTINGS_MODULE=%s, DEBUG=%s" % (os.getenv('DJANGO_SETTINGS_MODULE',''), settings.DEBUG))
    return django_wsgi.WSGIHandler()

def clock_demo(environ, start_response):
    start_response("200 OK", [('Content-type','text/plain')])
    # whatever empty file, we just want to receive a timeout
    fname = '/tmp/fifo'
    try:
        os.mkfifo(fname)
    except OSError:
        pass
    fd = os.open(fname, os.O_RDONLY | os.O_NONBLOCK)
    os.read(fd, 65535)
    try:
        while True:
            yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
            yield "%s\n" % (datetime.datetime.now(),)
    except GeneratorExit:
        pass
    os.close(fd)
    return

'''
# returning iterators doesn't work for turbogears and pylons, sorry
def wsgi_cherry_py():
    import pkg_resources
    import cherrypy
    import sys

    pkg_resources.require("TurboGears")

    from cherrypy._cpwsgi       import wsgiApp

    #if os.path.exists(os.path.join(os.getcwd(), "setup.py")):
    #    print 1
    #    cherrypy.config.update(file="dev.cfg")
    #else:
    cherrypy.config.update(file="prod.cfg")

    from tgproject.controllers import Root

    cherrypy.root = Root()

    cherrypy.server.start(initOnly=True, serverClass=None)
    return wsgiApp

def wsgi_pylons():
    from paste.deploy import loadapp
    return loadapp('config:%s' % (os.path.join(os.getcwd(), 'development.ini')))
'''

# after called, should return valid ``wsg_application(environ, start_response)`` function
FRAMEWORKS = {
    'django':wsgi_django,
    'demo':lambda: clock_demo,
}


def get_libevent_version(binary):
    libevent = ctypes.CDLL(binary)
    ver = libevent.event_get_version
    ver.restype = ctypes.c_char_p
    version = ver()[:]
    libevent.close()
    return version

'''
0. try users dir
1. try current directory
2. try LD_LIBRARY_PATH
3. try /usr/local/lib
4. normal dlopen(event)
'''

def find_libevent_binary(userpath):
    def getpath(userpath):
        if userpath:
            if os.path.isdir(userpath):
                return os.path.join(userpath, libeventbin)
            if os.path.isfile(userpath) or os.path.islink(userpath):
                return os.path.realpath(os.path.expanduser(userpath))
            raise Exception("%r is not a valid path to %s" % (userpath,libeventbin))

        if os.path.exists('./%s' % libeventbin):
            return './%s' % libeventbin

        if os.path.exists(resource_filename(__name__, libeventbin)):
            return resource_filename(__name__, libeventbin)

        try:
            a = ctypes.CDLL(libeventbin)
            a.close()
            return libeventbin
        except OSError:
            pass

        if os.path.exists('/usr/local/lib/%s' % libeventbin):
            return '/usr/local/lib/%s' % libeventbin

        try:
            so = ctypes.util.find_library('event')
            a = ctypes.CDLL(so)
            a.close()
            return so
        except OSError:
            pass

        return libeventbin

    so = getpath(userpath)
    try:
        ver = get_libevent_version(so)
        return so, ver
    except OSError:
        raise Exception("**** %r not found or can't be loaded ****\n" % (libeventbin)+
                        "                try setting the location using --libevent </path/to/the/%s> flag\n" % (libeventbin)+
                        "                or use 'LD_LIBRARY_PATH=\"../pathtolibeventsobinaries\" %s ...'.\n" % (sys.argv[0]) +
                        "                you can also try to install libevent in current directory %r or /usr/local/lib" % (os.getcwd()))




def main(args):
    usage = "usage: %prog [options]"
    desc = "evserver - Asynchronous WSGI http server usign libevent"
    parser = optparse.OptionParser(usage, description=desc)
    parser.add_option("-o", "--log", dest="logfile",
                      help="write the logs to the file")
    parser.add_option("-v", "--verbose",
                      action="count", dest="verbosity",
                      help="increase the verbosity of debugging")
    parser.add_option("-n", "--nodebug",
                      action="store_true", dest="nodebug",
                      help="disable setting verbosity is the noisiest level (aka debugging)")
    parser.add_option("-l", "--listen",
                      action="store", dest="addr", default="127.0.0.1:8080",
                      help="host:port to bind to (default is %default)")
    parser.add_option("-f", "--framework",
                      action="store", dest="framework",
                      help="wsgi framework to call on request, one of [%s]" % '|'.join(sorted(FRAMEWORKS.keys())))
    parser.add_option("-e", "--exec",
                      action="store", dest="frameexec",
                      help="chunk of python code that specifies wsgi entry point application(environ, start_response), used if no framework is specified")
    parser.add_option("", "--libevent",
                      action="store", dest="libeventbinary", default="",
                      help="use %s binary from specified path" % libeventbin)
    parser.add_option("-s", "--status",
                      action="store", dest="statusaddr", default="",
                      help="Bind server status page to specified host:port")
    parser.add_option("-p", "--psyco",
                      action="store_true", dest="psyco",
                      help="Try to enable Psyco just-in-time compiler.")
    parser.add_option("-r", "--reload",
                      action="count", dest="reload",
                      help="Enable automatic code reloader, useful for development. Use this option twice to force the application to die when code changes.")

    (options, left_args) = parser.parse_args(args=args)

    if left_args:
        parser.error("incorrect number of arguments")

    if not options.verbosity: options.verbosity = 0
    verbosity = 50-options.verbosity * 10
    verbosity = verbosity if verbosity > 0 else 1
    if not options.nodebug:
        verbosity = 10

    try:
        host, port = options.addr.split(':')
        port = int(port)
        if port < 0 or port > 65535: raise ValueError
    except (ValueError,):
        parser.error("Address ip:port in wrong format.")

    if options.statusaddr:
        try:
            shost, sport = options.statusaddr.split(':')
            sport = int(sport)
            if sport < 0 or sport > 65535: raise ValueError
        except (ValueError,):
            parser.error("Status address ip:port in wrong format.")

    # enable logging ASAP
    if options.logfile:
        logfilename = os.path.normpath(os.path.expanduser(options.logfile))
        logging.basicConfig(level=verbosity, format=FORMAT_FILE, filename=logfilename, filemode='a')
    else:
        logging.basicConfig(level=verbosity, format=FORMAT_CONS)

    if options.framework and options.frameexec:
        parser.error("Please use --framework OR --exec option.")
    if options.framework:
        if options.framework not in FRAMEWORKS:
            parser.error("Framework %r not supported. Availble ones are [%s]." % (options.framework, '|'.join(sorted(FRAMEWORKS.keys()))))
        application = FRAMEWORKS[options.framework]()
    elif options.frameexec:
        application = None
        exec(options.frameexec)
        if not application:
            parser.error("variable application() not defined by your code in --exec option.")
    else:
        parser.error("Please specify --framework or --exec parameters.")

    if options.psyco:
        try:
            import psyco
            psyco.full()
            log.info('Psyco enabled.')
        except ImportError:
            log.error('Psyco import failed.')


    log.info("Running with verbosity %i (>=%s)" % (verbosity, logging.getLevelName(verbosity)))
    log.info("Framework=%r, Main dir=%r, args=%r" % (options.framework, os.getcwd(), args))
    libeventbinary, libeventversion = find_libevent_binary(options.libeventbinary)
    ctypes.libeventbinary = libeventbinary
    ctypes.libeventbinary_version = libeventversion
    import server

    log.info("libevent loaded from %r, ver %r" % (libeventbinary, libeventversion,))
    server.main_init()

    if not options.nodebug:
        if options.verbosity:
            log.warning("ommiting -v options, because debugging is turned on")

    if options.reload:
        die = False if options.reload != 2 else True
        log.warning("Starting automatic code reloading. Die on change = %r" % (die, ))
        import reloader
        reloader.Reloader(die=die)

    if not options.statusaddr:
        server.main_loop( [(host, port, application),] )
    else:
        import status
        server.main_loop( [(host, port, application),
                            (shost, sport, status.wsgi_application)] )

if __name__ == "__main__":
    main(sys.argv[1:])

def egg_entry_point():
    main(sys.argv[1:])