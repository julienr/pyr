import tornado.ioloop
import tornado.web
import tornado.gen as gen
import tornado.escape as escape
import tornado.websocket as websocket
from tornado.web import URLSpec, asynchronous
import os
import sys
import StringIO
import jinja2
import mimetypes
import rpy2.robjects as robjects
import json

# Fake r initialization
robjects.globalenv['A'] = robjects.r.matrix(robjects.IntVector(range(10)), nrow=5)
robjects.globalenv['B'] = robjects.r.matrix(robjects.IntVector(range(10,0,-1)), nrow=5)

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

    def send_plot(self, fig):
        imgdata = StringIO.StringIO()
        fig.savefig(imgdata, format='png')
        imgdata.seek(0)
        self.send_file(imgdata.read(), 'image/png')

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

    def send_refresh_workspace(self):
        wsdict = list_workspace()
        response = {
            'type': 'workspace',
            'data' : wsdict
        }
        self.write_message(escape.json_encode(response))

    def send_reval_result(self, command):
        try:
            result = str(robjects.r(command))
        except Exception as e:
            result = str(e)

        response = {
            'type': 'evalresult',
            'data':result
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

# Standard handlers
class ListRWorkspace(RPYRequestHandler):
    def get(self):
        self.send_json(list_workspace())

class IndexPage(RPYRequestHandler):
    def get(self):
        self.render_template('index.html')


#class IndexPage(RPYRequestHandler):
    #def do_plot(self, seqname, segname, segidx, callback):
        #seq = get_sequence(seqname)
        #segmentation = seq.load_segmentation(segname)
        #segment = segmentation.get_segment(segidx)

        ## plot
        #fig = Figure()
        #canvas = FigureCanvas(fig)
        #ax = fig.add_subplot(111)
        #ax.plot(segment.data)
        #ax.set_title("%s/%s/%i" % (seqname, segname, segidx))
        #ax.set_xlabel('Sample index (segment-based)')
        #ax.set_ylabel('Value')
        #ax.set_xlim(0, segment.data.shape[0])
        #callback(fig)

    #@asynchronous
    #@gen.engine
    #def get(self, seqname, segname, segidx):
        #segidx = int(segidx)
        #fig = yield gen.Task(self.do_plot, seqname, segname, segidx)
        #self.send_plot(fig)

settings = {
    'static_path': os.path.join(os.path.dirname(__file__), 'static'),
    'debug': True,
}

application = tornado.web.Application([
        URLSpec(r"/", IndexPage, name='index'),
        URLSpec(r"/rworkspace",
                ListRWorkspace, name='rworkspace'),
        URLSpec(r"/rsocket",
                RSocket, name='rsocket')

        #URLSpec(r"/seq/(?P<seqname>\w+)",
                #SequenceHandler, name='sequence'),
        #URLSpec(r"/seq/(?P<seqname>\w+)/seg/(?P<segname>\w+)/dataplot",
                #SequenceDataplotHandler, name='sequence_dataplot'),
        #URLSpec(r"/seq/(?P<seqname>\w+)/seg/(?P<segname>\w+)",
                #SequenceSegmentationHandler, name="sequence_segmentation"),
        #URLSpec(r"/seq/(?P<seqname>\w+)/seg/(?P<segname>\w+)/(?P<segidx>\d+)/dataplot",
                #SequenceSegmentDataPlotHandler, name='sequence_segment_dataplot'),
        #URLSpec(r"/seq/(?P<seqname>\w+)/seg/(?P<segname>\w+)/(?P<segidx>\d+)/medimage",
                #SequenceSegmentMedimageHandler, name='sequence_segment_medimage'),
        #URLSpec(r"/seq/(?P<seqname>\w+)/seg/(?P<segname>\w+)/segments",
                #SequenceSegmentsPlotHandler, name='sequence_segments_plots')
    ],
    **settings)


if __name__ == '__main__':
    port = 8888
    application.listen(port, address='0.0.0.0')
    print 'Listening on port ', port
    tornado.ioloop.IOLoop.instance().start()

