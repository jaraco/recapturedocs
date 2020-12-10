import os
import sys
import functools
import itertools
import argparse
import contextlib
import inspect
import docutils.io
import docutils.core
import logging
import importlib
import code
import shlex
import socket
import urllib.parse
from typing import Dict

import pkg_resources
import cherrypy
import genshi.template
import boto
import jaraco.collections as dictlib
import jaraco.logging
from jaraco.classes import meta
from jaraco.email import notification

import recapturedocs
from . import model
from . import persistence
from . import aws
from . import config
from . import errors
from . import dropbox


class JobServer:
    """
    The job server is both a CherryPy server and a list of jobs
    """

    tl = genshi.template.TemplateLoader(
        [genshi.template.loader.package(__name__, 'view')]
    )

    @cherrypy.expose
    def index(self):
        tmpl = self.tl.load('main.xhtml')
        message = "Welcome to RecaptureDocs"
        return tmpl.generate(
            message=message,
            page_cost=model.MTurkConversionJob.page_cost,
            user_agent=cherrypy.request.user_agent,
            version=recapturedocs.version,
        ).render('xhtml')

    @staticmethod
    def construct_url(path):
        return urllib.parse.urljoin(cherrypy.request.base, path)

    @staticmethod
    def is_production():
        return cherrypy.config.get('server.production', False)

    @cherrypy.expose
    def upload(self, file, class_='MTurkConversionJob'):
        job_class = getattr(model, class_)
        server_url = self.construct_url('/process')
        content_type_map = dictlib.IdentityOverrideMap(
            {
                # some people have their browsers incorrectly configured with
                #  mime types, so map these types.
                'application/adobe': 'application/pdf',
                'application/x-pdf': 'application/pdf',
            },
        )
        content_type = content_type_map[str(file.content_type)]
        if content_type != 'application/pdf':
            msg = "Got content other than PDF: {content_type}"
            cherrypy.log(msg.format(**vars(file)), severity=logging.WARNING)
        job = job_class(file.file, content_type, server_url, file.filename)
        job.save_if_new()
        self.send_notice(f"A new document was uploaded ({job.id})")
        raise cherrypy.HTTPRedirect(f"status/{job.id}")

    @cherrypy.expose
    def status(self, job_id):
        tmpl = self.tl.load('status.xhtml')
        job = self._get_job_for_id(job_id)
        tmpl_gen = tmpl.generate(job=job, production=self.is_production())
        return tmpl_gen.render('xhtml')

    @cherrypy.expose
    def initiate_payment(self, job_id):
        """
        Given a job ID, redirect to a site to initiate payment for that
        job.
        """
        raise NotImplementedError()
        job = self._get_job_for_id(job_id)
        url = self.construct_payment_url(job)
        raise cherrypy.HTTPRedirect(url)

    @staticmethod
    def construct_payment_url(job):
        tmpl = 'RecaptureDocs conversion - {n_pages} pages'
        reason = tmpl.format(n_pages=len(job))
        return_url = f'/complete_payment/{job.id}'
        transaction_amount = str(float(job.cost))
        # TODO: construct URL from details
        raise NotImplementedError(locals())

    @cherrypy.expose
    def complete_payment(self, job_id, **params):
        job = self._get_job_for_id(job_id)
        # TODO: using params, process the payment
        success = params['success'] == 'true'
        if success:
            tmpl = self.tl.load('declined.xhtml')
            params_mk = genshi.Markup(f'<!-- {params} -->')
            res = tmpl.generate(job=job, params=params_mk)
            self.send_notice(f"Payment denied - {job.id}, {params}")
            return res.render('xhtml')
        # TODO: perform any additional validation and save
        # any details on the job.
        try:
            job.register_hits()
            target = f'/status/{job_id}'
        except errors.InsufficientFunds:
            self.send_notice(f"insufficient funds registering hits for {job_id}")
            target = '/error/our fault'
        job.save()
        raise cherrypy.HTTPRedirect(target)

    @cherrypy.expose
    def process_page(self, job_id, page_number):
        tmpl = self.tl.load('retype page.xhtml')
        params = dict(
            assignment_id=f'{job_id}-{page_number}',
            submit_url='submit_text',
        )
        return tmpl.generate(**params).render('xhtml')

    @cherrypy.expose
    def process(self, hitId, assignmentId, workerId=None, turkSubmitTo=None, **kwargs):
        """
        Fulfill a request of a client who's been sent from AMT. This
        will be rendered in an iFrame, so don't use the template.
        """
        preview = assignmentId == 'ASSIGNMENT_ID_NOT_AVAILABLE'
        submit_url = '{turkSubmitTo}/mturk/externalSubmit'.format(**vars())
        params = dict(
            assignment_id=assignmentId,
            hit_id=hitId,
            worker_id=workerId,
            preview=preview,
            submit_url=submit_url,
            page_url=f'/image/{hitId}' if not preview else '/static/Lorem ipsum.pdf',
        )
        cherrypy.log(f"params are {params}")
        tmpl = self.tl.load('retype page.xhtml')
        return tmpl.generate(**params).render('xhtml')

    def _get_job_for_id(self, job_id):
        return model.MTurkConversionJob.load(job_id)

    @cherrypy.expose
    def get_results(self, job_id):
        job = self._get_job_for_id(job_id)
        if not job.is_complete():
            return '<div>Job not complete</div>'
        cherrypy.response.headers['Content-Type'] = 'text/plain'
        return job.get_data()

    @cherrypy.expose
    def image(self, hit_id):
        # find the appropriate image
        job = model.MTurkConversionJob.for_hitid(hit_id)
        if not job:
            raise cherrypy.NotFound
        cherrypy.response.headers['Content-Type'] = job.content_type
        return job.page_for_hit(hit_id)

    @cherrypy.expose
    def design(self):
        return self.tl.load('design goals.xhtml').generate().render('xhtml')

    @cherrypy.expose
    def text(self, name):
        path = 'text/' + name + '.rst'
        rst = pkg_resources.resource_stream('recapturedocs', path)
        parts = docutils.core.publish_parts(
            source=rst,
            source_class=docutils.io.FileInput,
            writer_name='html',
        )
        html = genshi.HTML(parts['html_body'])
        tmpl = self.tl.load('simple.xhtml')
        return tmpl.generate(content=html).render('xhtml')

    def __iter__(self):
        return model.MTurkConversionJob.load_all()

    def __delitem__(self, key):
        jobs = list(iter(self))
        for job in jobs[key]:
            job.remove()

    @cherrypy.expose
    def error(self, why):
        tmpl = self.tl.load('simple.xhtml')
        message = (
            f"An error has occurred ({why}). We apologize for the "
            "inconvenience. Our staff has "
            "been notified and should be responding. Please try again "
            "later, or for immediate assistance, contact our support team."
        )
        return tmpl.generate(content=message).render('xhtml')

    def send_notice(self, msg):
        app_config = self._app.config
        if 'notification' not in app_config:
            return
        notn_config = app_config['notification']
        addr_to = notn_config['smtp_to']
        host = notn_config['smtp_host']
        mb = notification.SMTPMailbox(to_addrs=addr_to, host=host)
        mb.notify(msg)


class GGCServer:
    """
    Server for Global Giving Community with Dropbox-hosted jobs
    """

    tl = genshi.template.TemplateLoader(
        [
            genshi.template.loader.package(__name__, 'view/ggc'),
            genshi.template.loader.package(__name__, 'view'),
        ]
    )

    tokens: Dict[str, str] = dict()

    @cherrypy.expose
    def index(self):
        return '<a href="authorize">authorize</a>'

    @cherrypy.expose
    def authorize(self):
        sess = dropbox.get_session()
        request_token = sess.obtain_request_token()
        self.tokens[request_token.key] = request_token
        callback = cherrypy.url('save_token')
        url = sess.build_authorize_url(request_token, oauth_callback=callback)
        raise cherrypy.HTTPRedirect(url)

    @cherrypy.expose
    def save_token(self, oauth_token, uid, **kwargs):
        sess = dropbox.get_session()
        access_token = sess.obtain_access_token(self.tokens[oauth_token])
        persistence.store.dropbox.tokens.update(
            dict(
                _id=uid,
            ),
            dict(
                _id=uid,
                key=access_token.key,
                secret=access_token.secret,
            ),
            upsert=True,
        )
        info = dropbox.get_client(sess).account_info()
        tmpl = self.tl.load('simple.xhtml')
        message = "Welcome, {display_name}. Your account has now been linked.".format(
            **info
        )
        return tmpl.generate(content=message).render('xhtml')

    @cherrypy.expose
    def list(self):
        def pdf_list(client):
            md = client.metadata('/')
            info = client.account_info()['display_name']
            return (
                info,
                [
                    item['path']
                    for item in md['contents']
                    if item['mime_type'] == 'application/pdf'
                ],
            )

        lists = map(
            pdf_list, map(dropbox.load_client, persistence.store.dropbox.tokens.find())
        )
        tmpl = self.tl.load('list.xhtml')
        return tmpl.generate(lists=lists).render('xhtml')


class Admin:
    tl = genshi.template.TemplateLoader(
        [
            genshi.template.loader.package(__name__, 'view/admin'),
            genshi.template.loader.package(__name__, 'view'),
        ]
    )

    def __init__(self, server):
        self.server = server

    @cherrypy.expose
    def status(self):
        tmpl = self.tl.load('status.xhtml')
        return tmpl.generate(jobs=list(self.server)).render('xhtml')

    @cherrypy.expose
    def disable_all(self):
        """
        Disable of all recapture-docs hits (even those not recognized by this
        server).
        """
        disabled = model.RetypePageHIT.disable_all()
        del self.server[:]
        return (
            'Disabled {disabled} HITs (do not forget to remove them '
            'from other servers).'
        ).format(**locals())

    @cherrypy.expose
    def pay(self, job_id):
        """
        Force payment for a given job.
        """
        job = self.server._get_job_for_id(job_id)
        job.authorized = True
        job.register_hits()
        return (
            f'<a href="/status/{job_id}">Payment simulated; click here for status.</a>'
        )


@contextlib.contextmanager
def start_server(configs):
    """
    The main entry point for the service, regardless of how it's used.
    Takes any number of filename or dictionary objects suitable for
    cherrypy.config.update.
    """
    importlib.import_module('.agency', __package__)
    aws.set_connection_environment()
    server = JobServer()
    if hasattr(cherrypy.engine, "signal_handler"):
        cherrypy.engine.signal_handler.subscribe()
    if hasattr(cherrypy.engine, "console_control_handler"):
        cherrypy.engine.console_control_handler.subscribe()
    app = cherrypy.tree.mount(server, '/')
    server._app = app
    list(map(app.merge, configs))
    admin_app = cherrypy.tree.mount(Admin(server), '/admin')
    passwords = cherrypy.lib.auth_basic.checkpassword_dict(
        dict(
            admin='g0tch4-h4x0r',
        )
    )
    devel_configs = list(configs) + [
        {
            '/': {
                'tools.auth_basic.on': True,
                'tools.auth_basic.realm': 'RecaptureDocs admin',
                'tools.auth_basic.checkpassword': passwords,
            },
        }
    ]
    list(map(admin_app.merge, devel_configs))
    cherrypy.tree.mount(GGCServer(), '/ggc')
    if not cherrypy.config.get('server.production', False):
        boto.set_stream_logger('recapturedocs')
        aws.ConnectionFactory.production = False
    server.send_notice(
        "RecaptureDocs {version} server starting on {hostname}".format(
            hostname=socket.getfqdn(),
            version=pkg_resources.require('recapturedocs')[0].version,
        )
    )
    cherrypy.engine.start()
    yield server
    cherrypy.engine.exit()


class Command(metaclass=meta.LeafClassesMeta):
    def __init__(self, *configs):
        self.configs = configs
        self.configure()

    def configure(self):
        """
        Initialize the cherrypy context and other configuration options
        based on the cherrypy config items supplied.
        """
        # set the socket host, but let other configs override
        host_config = {
            'global': {
                'server.socket_host': '::0',
                'log.screen': False,
                # genshi generates utf-8 by default, so let's instruct the
                #  browser that's what we're using as well.
                'tools.encode.on': True,
                'tools.encode.encoding': 'utf-8',
                'tools.agent_parser.on': True,
            },
        }
        static_dir = pkg_resources.resource_filename('recapturedocs', 'static')
        static_config = {
            '/static': {'tools.staticdir.on': True, 'tools.staticdir.dir': static_dir},
        }
        self.configs = list(itertools.chain([host_config, static_config], self.configs))
        list(map(cherrypy.config.update, self.configs))
        # save a copy of the whole config so the persistence module can find
        #  its config values.
        # TODO: consider doing persistence setup as a cherrypy plugin
        cherrypy._whole_config = cherrypy.lib.reprconf.Config()
        list(map(cherrypy._whole_config.update, self.configs))
        persistence.init()

    @classmethod
    def add_subparsers(cls, parser):
        subparsers = parser.add_subparsers()
        [cmd_class.add_parser(subparsers) for cmd_class in cls._leaf_classes]

    @classmethod
    def add_parser(cls, subparsers):
        parser = subparsers.add_parser(cls.__name__.lower())
        parser.set_defaults(action=cls)
        parser.add_argument(
            '-C',
            '--package-config',
            dest="package_configs",
            default=[],
            action="append",
            type=get_package_config,
            help="Add config recipe as found in the package (e.g. prod)",
        )
        parser.add_argument('configs', nargs='*', default=[], help='Config filename')


class Serve(Command):
    def run(self):
        with start_server(self.configs):
            cherrypy.engine.block()
        raise SystemExit(0)


class Interact(Command):
    def configure(self):
        # change some config that's problemmatic in interactive mode
        g_config = {
            'global': {'autoreload.on': False, 'log.screen': False},
        }
        self.configs = list(itertools.chain([g_config], self.configs))
        super(Interact, self).configure()

    def run(self):
        with start_server(self.configs) as server:
            # although the client could get the server from
            # cherrypy.tree.apps[''].root, let's make an alias
            globals().update(server=server)
            code.interact(local=globals())


class Daemon(Command):
    def run(self):
        from cherrypy.process.plugins import Daemonizer

        d = Daemonizer(
            cherrypy.engine,
            stdout=config.get_log_file(),
            stderr=config.get_error_file(),
        )
        d.subscribe()
        with start_server(self.configs):
            cherrypy.engine.block()


def get_package_config(name):
    name = name if name.endswith('.conf') else name + '.conf'
    pkg_res = functools.partial(pkg_resources.resource_filename, 'recapturedocs')
    return pkg_res(name)


def command_line():
    """
    Heroku only allows an application to deviate based
    on environment variables, so we allow command-line
    args to be specified as env vars.
    """
    return sys.argv[1:] + (shlex.split(os.environ.get('COMMAND_LINE_ARGS', '')))


def handle_command_line():
    usage = inspect.getdoc(handle_command_line)
    parser = argparse.ArgumentParser(usage=usage)
    jaraco.logging.add_arguments(parser)
    Command.add_subparsers(parser)
    args = parser.parse_args(command_line())
    jaraco.logging.setup(args)
    user_configs = args.package_configs + args.configs
    command = args.action(*user_configs)
    command.run()


if __name__ == '__main__':
    handle_command_line()
