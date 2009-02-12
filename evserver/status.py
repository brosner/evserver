'''
webpy
python-pydot
'''
import web
import server
import time
import gc
import os
import resource

import other.objgraph as objgraph
import other.meminfo as meminfo
import inspect
import random
import collections
import operator
import urllib

urls = (
    '/$', 'status_page',
    '/memleaks/$', 'memleaks_page',
    '/memleaks/([^/]+)/$', 'memleaks_type_page',
)


class status_page:
    def GET(self):
        web.header('Content-Type','text/plain', unique=True)
        web.header('Refresh','3')
        s = []
        resources = dict(zip(
                ('utime', 'stime', 'maxrss', 'ixrss','idrss','isrss','minflt','majflt','nswap','inblock','outblock','msgsnd','msgrcv','nsignals','nvcsw','nivcsw'),
                resource.getrusage(resource.RUSAGE_SELF)))

        pid, pagesize = os.getpid(), resource.getpagesize()

        vm, rm, sm = meminfo.memory()
        gc0, gc1, gc2 = gc.get_count()
        s.append(
        '''######## PID:%(pid)i  total events:%(event_counter)i  python objects, unreachable:%(gc_unreachable)i total:%(gc_objects)i dirty:%(gc0)i/%(gc1)i/%(gc2)i file descriptors:%(file_descriptors)i/%(max_descriptors)i \n'''
        '''######## virt memory:%(vm).0fMiB  res memory:%(rm).0fMiB  sys cpu time:%(sys).3fs  user:%(user).3fs context switches, voluntary:%(vcs)i  involuntary:%(ics)i \n''' %
            {
                'pid':pid,
                'event_counter':server.event_counter,
                'gc0': gc0,
                'gc1': gc1,
                'gc2': gc2,
                'gc_unreachable': len(gc.garbage),
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

        s.append("took %.3fms\n" % ((time.time()-web.ctx.environ['wsgi.now']())*1000.0, ))
        return ''.join(s)

class memleaks_page:
    def GET(self):
        web.header('Content-Type','text/html', unique=True)
        gc.collect()
        gc.collect()
        gc.collect()

        
        typestats = collections.defaultdict(lambda: 0)
        for o in gc.garbage:
            typestats[type(o).__name__] += 1

        forgotten_items = sorted(typestats.items(), key=operator.itemgetter(1), reverse=True)

        used_items = objgraph.show_most_common_types(limit=50)
        if not used_items: used_items = []

        s = []
        for name, items in [('gc.garbage -> Not collectable items',forgotten_items), 
                            ('gc.get_objects -> Collectable items',used_items)]:
            s.append('''<h3>%s</h3><br/>\n''' % name)
            for typename, number in items:
                s.append('''%i: <a href="./%s/">%s</a><br/>\n''' % (number, urllib.quote(typename), typename))
        

        return ''.join(s)

class memleaks_type_page:
    def GET(self, typename):
        web.header('Content-Type','image/png', unique=True)
        gc.collect()
        gc.collect()
        gc.collect()
        print '%r ' % typename
        obj = random.choice(objgraph.by_type(typename))
        objgraph.show_backrefs([obj], max_depth=10)
        
        f = open('objects.png', 'rb')
        data = f.read()
        f.close()

        return data


# webpy 0.3 specific
wsgi_application = web.application(urls, globals()).wsgifunc()







