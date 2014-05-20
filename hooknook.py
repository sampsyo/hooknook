import flask
from flask import request, g
import threading
import enum
import queue
import click

app = flask.Flask(__name__)


class Command(enum.Enum):
    echo = 1


class Worker(threading.Thread):
    def __init__(self):
        super(Worker, self).__init__()
        self.daemon = True
        self.queue = queue.Queue()

    def run(self):
        while True:
            args = self.queue.get()
            self.handle(*args)

    def handle(command, *args):
        if command == Command.echo:
            print(args)

    def send(self, *args):
        self.queue.put(args)


@app.before_first_request
def _setup():
    g.worker = Worker()
    g.worker.start()


@app.route('/hook', methods=['POST'])
def hook():
    payload = request.get_json()
    g.worker.send(Command.echo, payload['repository']['name'])
    return flask.jsonify(status='success')


@click.command()
@click.argument('host', default='0.0.0.0')
@click.argument('port', default=5000)
def run(host, port):
    app.run(host=host, port=port)


if __name__ == '__main__':
    run()
