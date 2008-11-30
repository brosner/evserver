


import sys
import time
import stat
import imp
import ctypes

import os, os.path, logging
log = logging.getLogger(os.path.basename(__file__))


import server
import utils
libevent = server.libevent

# this two functions can leak memory, if you forget to free event_key on close
def event_callback(fd, evt, userdata_key):
    user_callback, _, _ = utils.get_and_del_userdata(userdata_key)
    user_callback(True if evt and (evt & libevent.EV_TIMEOUT) else False)
    return 0
event_callback_ptr = server.EVENT_CALLBACK(event_callback)

def event_schedule(fd, timeout, user_callback):
    byref_timev = None
    if timeout is not None:
        timev = libevent.timeval()
        timev.tv_sec  = int(timeout)
        timev.tv_usec = int((timeout - int(timeout)) * 1000000)
        byref_timev = ctypes.byref(timev)

    event = libevent.event()
    byref_event = ctypes.byref(event)

    event_key = utils.set_userdata( (user_callback, byref_event, byref_timev) )
    libevent.event_set(byref_event, fd, libevent.EV_READ, event_callback_ptr, event_key)
    libevent.evtimer_add(byref_event, byref_timev)
    return lambda : utils.get_and_del_userdata(userdata_key)


class FamPyinotify:
    ''' file-access-monitor based on PyInotify '''
    filenames = None
    onchange = None

    def __init__(self, onchange):
        log.debug('Starting file alteration monitor: FamPyinotify')
        self.filenames = {}

        class PTmp(ProcessEvent):
            def process_IN_CLOSE_WRITE(self, event):
                onchange(event.pathname)
            def process_IN_MODIFY(self, event):
                onchange(event.pathname)
        self.p = PTmp()
        self.wm = WatchManager()
        self.notifier = Notifier(self.wm, self.p)

    def add_file(self, fname):
        if fname in self.filenames:
            return False
        self.filenames[fname] = True
        self.wm.add_watch(fname, IN_CLOSE_WRITE, rec=True) # IN_MODIFY|
        return True

    def get_fd(self):
        return self.wm._fd

    def get_timeout(self):
        return None # no timeout, wait forever

    def close(self):
        del(self.p)
        del(self.wm)
        self.notifier.close()
        del(self.notifier)

    def update(self, timeout):
        self.notifier.read_events()
        self.notifier.process_events()

class FamPolling:
    ''' file-access-monitor based on polling access times for the files '''
    filenames = None
    onchange = None
    fd = None

    def __init__(self, onchange):
        log.debug('Starting file alteration monitor: FamPolling (files checked once a second)')
        self.filenames = {}
        self.onchange = onchange
        fname = '/tmp/fifo'
        try:
            os.mkfifo(fname)
        except OSError:
            pass
        self.fd = os.open(fname, os.O_RDONLY | os.O_NONBLOCK)

    def add_file(self, fname):
        if fname in self.filenames:
            return False
        self.filenames[fname] = os.stat(fname)[stat.ST_MTIME]

    def get_fd(self):
        return self.fd

    def get_timeout(self):
        return 1.0 # one second

    def close(self):
        os.close(self.fd)
        del self.fd

    def update(self, timeout):
        for fname, v in self.filenames.items():
            m = os.stat(fname)[stat.ST_MTIME]
            if v != m:
                self.filenames[fname] = m
                self.onchange(fname)

try:
    from other.pyinotify import WatchManager, Notifier, ProcessEvent, IN_MODIFY, IN_CLOSE_WRITE
except ImportError:
    FamDefault = FamPolling
else:
    FamDefault = FamPyinotify




import __builtin__

class Reloader:
    def __init__(self, die=False):
        self.die = die
        self.start()
        fd, timeout = self.get_fd_timeout()
        event_schedule(fd, timeout, self.update)

    def update(self, timeout):
        self.toreload = {}
        self.fam.update(timeout)
        if self.toreload and self.die:
            log.warning("Code has been changed in file %r. Quitting gracefully." % (self.toreload.keys()[0]))
            libevent.event_loopexit(None)
        else:
            for fname, module in self.toreload.items():
                log.warning("Reloading file %r, module %r" % (fname, module))
                reload(module)

            fd, timeout = self.get_fd_timeout()
            event_schedule(fd, timeout, self.update)

    def start(self):
        ''' things got quite messy here, don't try to understand the flow, sorry
        the main point is that when, during new import, we know the file to import,
        we still don't know the module and module name.
        '''
        cache = {} # 'file.py' -> <module>
        def add_file(pyc_file, module):
            fname = pyc_file.rpartition('.')[0] + '.py'
            if fname not in cache and os.access(fname, os.W_OK):
                log.warning("watching file %r" % (fname))
                self.fam.add_file(fname)
            cache[fname] = module

        def onchange(fname):
            self.toreload[fname] = cache[fname]

        self.fam = FamDefault(onchange)

        # fill cache
        for fname, module in [(m.__file__, m) for k, m in sys.modules.items() if m and getattr(m, '__file__', None)]:
            add_file(fname, module)


        # sorry about that, but I haven't found any better working solution
        self.orginal_import = __builtin__.__import__
        def new_import(*args,**kwargs):
            mod = self.orginal_import(*args, **kwargs)
            if mod and getattr(mod, '__file__', None):
                add_file(mod.__file__, mod)
            return mod
        __builtin__.__import__ = new_import
        return

    def get_fd_timeout(self):
        return (self.fam.get_fd(), self.fam.get_timeout())

    def stop(self):
        __builtin__.__import__ = self.orginal_import
        self.fam.close()



