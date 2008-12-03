import server
import time
import gc
import os
import resource
import meminfo
import other.objgraph as objgraph
import random

def wsgi_application(environ, start_response):
    if 'memleaks' in environ.get('PATH_INFO', ''):
        return memleaks(environ, start_response)
    else:
        return status_page(environ, start_response)

import inspect

def memleaks(environ, start_response):
    start_response("200 OK", [('Content-Type', 'text/plain')])
    gc.collect()
    gc.collect()
    gc.collect()
    b = objgraph.show_most_common_types(limit=50)
    if not b:
        b = []
    #return ['\n'.join(map(str,b))] #[ '\n\n'.join(['\n'.join(map(str,b)), '\n'.join(map(str, ob)), '\n'.join(ch)] ) ]
    ob = objgraph.by_type('tuple')
    ab = []
    if ob:
        for i in range(10):
            ab.append( ob[random.randint(0, len(ob)-1)] )
    print '%r' % ab
    if ab:
        objgraph.show_backrefs(ab, max_depth=18)
        #ch = objgraph.find_backref_chain(ob[0], inspect.ismodule)
        #if ch:
        #    ch = map(str, ch)
        #else:
    return ['\n'.join(map(str,b))] #[ '\n\n'.join(['\n'.join(map(str,b)), '\n'.join(map(str, ob)), '\n'.join(ch)] ) ]

def status_page(environ, start_response):
    start_response("200 OK", [('Content-Type', 'text/plain'), ('Refresh', '3')])
    s = []
    resources = dict(zip(
            ('utime', 'stime', 'maxrss', 'ixrss','idrss','isrss','minflt','majflt','nswap','inblock','outblock','msgsnd','msgrcv','nsignals','nvcsw','nivcsw'),
            resource.getrusage(resource.RUSAGE_SELF)))

    pid = os.getpid()
    pagesize = resource.getpagesize()

    vm, rm, sm = meminfo.memory()
    s.append(
    '''######## PID:%(pid)i  total events:%(event_counter)i  objects in memory:%(gc_objects)i  file descriptors:%(file_descriptors)i/%(max_descriptors)i \n'''
    '''######## virt memory:%(vm).0fMiB  res memory:%(rm).0fMiB  sys cpu time:%(sys).3fs  user:%(user).3fs context switches, voluntary:%(vcs)i  involuntary:%(ics)i \n''' %
        {
            'pid':pid,
            'event_counter':server.event_counter,
            'gc_objects':len(gc.get_objects()),
            'file_descriptors':len(os.listdir('/proc/%i/fd' % pid)),
            'max_descriptors':resource.getrlimit(resource.RLIMIT_NOFILE)[1],
            'vm': vm/1048576.0,
            'rm': rm/1048576.0,
            'sm': sm/1048576.0,
            'vcs':resources['nvcsw'],
            'ics':resources['nivcsw'],
            'sys':resources['stime'],
            'user':resources['utime'],
        },
    )

    for vhostdata in server.vhosts:
        s.append('''    **** %(host)s:%(port)i connections:%(counter)i broken:%(broken)i cpu_time:%(cpu_time).3fs ****\n''' % vhostdata)

        for clock, req in vhostdata['requests'].items():
            s.append('''        %(host)s:%(port)5s "%(method)s %(url)s %(http)s" %(status_code)3i %(content_length)8i/%(chunks)i/%(context_switches)i  (%(cpu_time).3fms)\n''' % {
                'host':req.environ['REMOTE_HOST'],
                'port':req.environ['REMOTE_PORT'],
                'method': req.environ['REQUEST_METHOD'],
                'url': req.get_url(),
                'http': req.environ['SERVER_PROTOCOL'],
                'status_code': req.out_dict['code'],
                'content_length':req.content_length,
                'chunks':req.chunks_number,
                'context_switches':req.context_switches,
                'cpu_time':req.all_cpu_time * 1000.0,
            })

        s.append('\n\n')

    s.append("took %.3fms\n" % ((time.time()-req.environ['wsgi.now']())*1000.0, ))
    return [''.join(s)]






