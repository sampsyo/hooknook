import flask
from flask import request, g
import threading
import queue
import click
import os
import subprocess
import traceback
import yaml
import datetime

app = flask.Flask(__name__)
app.config.update(
    DATA_DIR = os.path.expanduser(os.path.join('~', '.hooknook')),
    CONFIG_FILENAME = '.hook.yaml',
    CONFIG_DEFAULT = {
        'deploy': 'make deploy',
    },
)


def load_config(repo_dir):
    """Load the repository's configuration as a dictionary. Defaults are
    used for missing keys.
    """
    # Provide defaults.
    config = dict(app.config['CONFIG_DEFAULT'])

    # Load the configuration file, if any.
    config_fn = os.path.join(repo_dir, app.config['CONFIG_FILENAME'])
    if os.path.exists(config_fn):
        with open(config_fn) as f:
            overlay = yaml.load(f)
        config.update(overlay)

    return config


def timestamp():
    """Get a string indicating the current time.
    """
    now = datetime.datetime.now()
    return now.strftime('%Y-%m-%d-%H-%M-%S-%f')


def update_repo(repo, url):
    """Clone or pull the repository. Return the updated repository
    directory.
    """
    # Create the parent directory for repositories.
    parent = os.path.join(app.config['DATA_DIR'], 'repo')
    if not os.path.exists(parent):
        os.makedirs(parent)

    # Clone the repository or update it.
    repo_dir = os.path.join(parent, repo)
    # FIXME log
    if os.path.exists(repo_dir):
        subprocess.check_call(
            ['git', 'fetch'], cwd=repo_dir
        )
        subprocess.check_call(
            ['git', 'reset', '--hard', 'origin/master'],
            cwd=repo_dir,
        )
    else:
        subprocess.check_call(
            ['git', 'clone', url, repo_dir],
        )

    return repo_dir


def run_build(repo_dir):
    """Run the build in the repository direction.
    """
    # Get the configuration.
    config = load_config(repo_dir)

    # Run the build.
    try:
        subprocess.check_call(
            config['deploy'],
            shell=True,
            cwd=repo_dir,
        )
    except subprocess.CalledProcessError as exc:
        app.logger.error(
            'Deploy exited with status {}'.format(exc.returncode)
        )


def open_log(repo):
    """Open a log file for a build and return the open file.

    `repo` is the (filename-safe) name of the repository.
    """
    # Create the parent directory for the log files.
    parent = os.path.join(app.config['DATA_DIR'], 'log')
    if not os.path.exists(parent):
        os.makedirs(parent)

    # Get a log file for this build.
    ts = timestamp()
    log_fn = os.path.join(parent, '{}-{}.log'.format(repo, ts))

    return open(log_fn, 'w')


class Worker(threading.Thread):
    """Thread used for invoking builds asynchronously.
    """
    def __init__(self):
        super(Worker, self).__init__()
        self.daemon = True
        self.queue = queue.Queue()

    def run(self):
        while True:
            try:
                self.handle(*self.queue.get())
            except:
                app.logger.error(
                    'Worker exception:\n' + traceback.format_exc()
                )

    def handle(self, repo, url):
        """Execute a build.

        `repo` is the (filename-safe) repository name. `url` is the git
        clone URL for the repo.
        """
        app.logger.info('Building {}'.format(repo))

        with open_log(repo) as log:
            repo_dir = update_repo(repo, url)
            run_build(repo_dir)


    def send(self, *args):
        self.queue.put(args)


@app.before_request
def _setup():
    if not hasattr(g, 'worker'):
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
    if 'repository' in payload:
        g.worker.send(
            '{}-{}'.format(
                payload['repository']['owner']['name'],
                payload['repository']['name']
            ),
            payload['repository']['url'],
        )
    return flask.jsonify(status='success')


@click.command()
@click.argument('host', default='0.0.0.0')
@click.argument('port', default=5000)
@click.option('--debug', '-d', is_flag=True)
def run(host, port, debug):
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run()
