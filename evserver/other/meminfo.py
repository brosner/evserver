import os
#from http://code.activestate.com/recipes/286222/

_proc_status = '/proc/%d/status' % os.getpid()

_scale = {'kB': 1024.0, 'mB': 1024.0*1024.0,
          'KB': 1024.0, 'MB': 1024.0*1024.0}

def _memory():
    global _proc_status, _scale
     # get pseudo file  /proc/<pid>/status
    try:
        t = open(_proc_status)
        s = t.read()
        t.close()
    except:
        return 0.0  # non-Linux?
    # get VmKey line e.g. 'VmRSS:  9999  kB\n ...'
    r = []
    for key in ['VmSize:', 'VmRSS:', 'VmStk:']:
        i = s.index(key)
        v = s[i:].split(None, 3)  # whitespace
        if len(v) < 3:
            r.append(0.0)
        else:
            r.append(int (float(v[1]) * _scale[v[2]]) )
    return r


def memory():
    try:
        return _memory()
    except Exception:
        return 0,0,0
