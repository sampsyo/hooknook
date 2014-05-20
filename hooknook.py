import flask
from flask import request, g
import threading
import queue
import click
import os

app = flask.Flask(__name__)
app.config.update(
    DATA_DIR = os.path.expanduser(os.path.join('~', '.hooknook')),
)


class Worker(threading.Thread):
    def __init__(self):
        super(Worker, self).__init__()
        self.daemon = True
        self.queue = queue.Queue()

    def run(self):
        while True:
            self.handle(self.queue.get())

    def handle(args):
        print(args)
        print(app.config['DATA_DIR'])

    def send(self, *args):
        self.queue.put(args)


@app.before_first_request
def _setup():
    g.worker = Worker()
    g.worker.start()


@app.route('/hook', methods=['POST'])
def hook():
    event_type = request.headers.get('X-GitHub-Event')
    if not event_type:
        log.info('Received a non-hook request')
        return flask.jsonify(status='not a hook'), 403
    elif event_type == 'ping':
        return flask.jsonify(ping='pong')

    # FIXME Validate GitHub request origin.

    payload = request.get_json()
    app.logger.info(payload)
    if 'repository' in payload:
        g.worker.send(payload['repository']['owner'],
                      payload['repository']['name'])
    return flask.jsonify(status='success')


@click.command()
@click.argument('host', default='0.0.0.0')
@click.argument('port', default=5000)
@click.option('--debug', '-d', is_flag=True)
def run(host, port, debug):
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run()
