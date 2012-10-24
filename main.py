import tornado.ioloop
import tornado.web
import tornado.gen as gen
import tornado.escape as escape
import tornado.websocket as websocket
from tornado.web import URLSpec, asynchronous
import os
import os.path
import sys
import StringIO
import jinja2
import mimetypes
import rpy2.robjects as robjects
import json
import watchdog.observers
import watchdog.events
import tempfile

sockets = []

# Fake r initialization
robjects.globalenv['A'] = robjects.r.matrix(robjects.IntVector(range(10)), nrow=5)
robjects.globalenv['B'] = robjects.r.matrix(robjects.IntVector(range(10,0,-1)), nrow=5)

plotdir = os.path.abspath('tmp/rplots/')
#plotdir = tempfile.mkdtemp()

print 'plotdir : ', plotdir
# R plot setup
def set_plot2png():
    #robjects.r('pdf(file="tmp/rplots/plot%03d.pdf", onefile=FALSE)')
    #robjects.r('png(filename="%s/plot%%03d.png")'%plotdir)
    _, fname = tempfile.mkstemp(suffix='.png', dir=plotdir)
    robjects.r('png(filename="%s")'%fname)
set_plot2png()

class NewPlotHandler(watchdog.events.FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith('.png'):
            print 'new plot : ', event.src_path
            for s in sockets:
                s.send_new_plot(os.path.basename(event.src_path))

newplot_handler = NewPlotHandler()
observer = watchdog.observers.Observer()
observer.schedule(newplot_handler, plotdir, recursive=False)
observer.start()


# Jinja setup
jinja_env = jinja2.Environment(loader=jinja2.PackageLoader('pyr',
                                                           'templates'))

def url_for(handler_name, *args):
    return application.reverse_url(handler_name, *args)

class RPYRequestHandler(tornado.web.RequestHandler):
    def render_template_to_string(self, filename, **args):
        # Make some custom functions accessible from the template
        args['url_for'] = url_for
        args['static_url'] = self.static_url

        template = jinja_env.get_template(filename)
        return template.render(**args)

    def render_template(self, filename, **args):
        self.write(self.render_template_to_string(filename, **args))
        self.finish()

    def send_file(self, data, mimetype):
        self.set_header('Content-Type', mimetype)
        self.write(data)
        self.finish()

    def send_json(self, data):
        self.set_header('Content-Type', 'application/json')
        # http://www.tornadoweb.org/documentation/_modules/tornado/escape.html
        self.write(escape.json_encode(data))
        self.finish()

def list_workspace():
    matrices = {}
    strobjs = {}

    for name in robjects.r.ls(robjects.globalenv):
        print name
        obj = robjects.r[name]
        if isinstance(obj, robjects.vectors.Matrix):
            matrices[name] = {'cmajordata' : list(obj),
                          'nrow' : obj.nrow,
                          'ncol' : obj.ncol}
        else:
            strobjs[name] = obj.r_repr()

    return {'matrices':matrices, 'strobjs':strobjs}

## Handlers
# Websocket
# http://blog.kagesenshi.org/2011/10/simple-websocket-push-server-using.html
class RSocket(websocket.WebSocketHandler):
    def open(self):
        print 'WebSocket opened'
        sockets.append(self)

    def send_refresh_workspace(self):
        wsdict = list_workspace()
        response = {
            'type': 'workspace',
            'data' : wsdict
        }
        self.write_message(escape.json_encode(response))

    def send_reval_result(self, command):
        # TODO: This is ugly, but the only way to ensure we continue plotting
        # to files if the user calls dev.off()
        set_plot2png()

        try:
            result = str(robjects.r(command))
        except Exception as e:
            result = str(e)

        response = {
            'type': 'evalresult',
            'data':result
        }
        self.write_message(escape.json_encode(response))

    def send_new_plot(self, plot_path):
        response = {
            'type': 'plot',
            'data' : url_for('rplot', plot_path)
        }
        self.write_message(escape.json_encode(response))

    def on_message(self, message):
        msg = escape.json_decode(message)
        print msg
        if msg['type'] == 'refreshws':
            self.send_refresh_workspace()
        elif msg['type'] == 'submit':
            data = msg['data']
            self.send_reval_result(data)
            self.send_refresh_workspace()

    def on_close(self):
        print 'WebSocket closed'
        sockets.remove(self)

# Standard handlers
class ListRWorkspace(RPYRequestHandler):
    def get(self):
        self.send_json(list_workspace())

class RPlot(RPYRequestHandler):
    def load_plot(self, plotname, callback):
        contents = None
        with open(os.path.join(plotdir, plotname), 'rb') as f:
            contents = f.read()
        callback(contents)

    @asynchronous
    @gen.engine
    def get(self, plotname):
        imgdata = yield gen.Task(self.load_plot, plotname)
        self.send_file(imgdata, 'image/png')


class IndexPage(RPYRequestHandler):
    def get(self):
        self.render_template('index.html')

settings = {
    'static_path': os.path.join(os.path.dirname(__file__), 'static'),
    'debug': True,
}

application = tornado.web.Application([
        URLSpec(r"/", IndexPage, name='index'),
        URLSpec(r"/rworkspace",
                ListRWorkspace, name='rworkspace'),
        URLSpec(r"/rsocket",
                RSocket, name='rsocket'),
        URLSpec(r"/rplot/(?P<plotname>[\w\d\._-]+)",
                RPlot, name="rplot"),
    ],
    **settings)


if __name__ == '__main__':
    port = 8888
    application.listen(port, address='0.0.0.0')
    print 'Listening on port ', port
    tornado.ioloop.IOLoop.instance().start()

