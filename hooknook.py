import flask
from flask import request
import threading
import queue
import click
import os
import subprocess
import traceback
import yaml
import datetime
import netaddr
import requests
import string
import random
import urllib.parse

app = flask.Flask(__name__)
app.config.update(
    DATA_DIR=os.path.expanduser(os.path.join('~', '.hooknook')),
    CONFIG_FILENAME='.hook.yaml',
    CONFIG_DEFAULT={
        'deploy': 'make deploy',
    },
    USERS=(),
    FILENAME_FORMAT='{user}#{repo}',
    PRIVATE_URL_FORMAT='git@github.com:{user}/{repo}.git',
    PUBLIC_URL_FORMAT='https://github.com/{user}/{repo}.git',
    GITHUB_ID=None,
    GITHUB_SECRET=None,
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


def shell(command, logfile, cwd=None, shell=False):
    """Execute a command (via a shell or directly) and log the stdout
    and stderr streams to a file-like object.
    """
    if shell:
        logline = command
    else:
        logline = ' '.join(command)
    logfile.write('$ {}\n'.format(logline))
    logfile.flush()

    subprocess.check_call(
        command,
        cwd=cwd,
        stdout=logfile,
        stderr=subprocess.STDOUT,
        shell=shell,
    )
    logfile.flush()


def random_string(length=20, chars=(string.ascii_letters + string.digits)):
    return ''.join(random.choice(chars) for i in range(length))


def github_get(path, token=None, base='https://api.github.com'):
    """Make a request to the GitHub API."""
    token = token or flask.session['github_token']
    url = '{}/{}'.format(base, path)
    return requests.get(url, params={
        'access_token': token,
    })


def update_repo(repo, url, log):
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
        shell(['git', 'fetch'], log, repo_dir)
        shell(['git', 'reset', '--hard', 'origin/master'], log, repo_dir)
    else:
        shell(['git', 'clone', url, repo_dir], log)

    return repo_dir


def run_build(repo_dir, log):
    """Run the build in the repository direction.
    """
    # Get the configuration.
    config = load_config(repo_dir)

    # Run the build.
    try:
        shell(config['deploy'], log, repo_dir, True)
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
        """Wait for jobs and execute them with `handle`.
        """
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
            repo_dir = update_repo(repo, url, log)
            run_build(repo_dir, log)

    def send(self, *args):
        """Add a job to the queue.
        """
        self.queue.put(args)


@app.before_first_request
def app_setup():
    """Ensure that the application has some shared global attributes set
    up:

    - `worker` is a Worker thread
    - `github_networks` is the list of valid origin IPNetworks
    """
    # Create a worker thread.
    if not hasattr(app, 'worker'):
        app.worker = Worker()
        app.worker.start()

    # Load the valid GitHub hook server IP ranges from the GitHub API.
    if not hasattr(app, 'github_networks'):
        meta = requests.get('https://api.github.com/meta').json()
        app.github_networks = []
        for cidr in meta['hooks']:
            app.github_networks.append(netaddr.IPNetwork(cidr))
        app.logger.info(
            'Loaded GitHub networks: {}'.format(len(app.github_networks))
        )


@app.route('/hook', methods=['POST'])
def hook():
    """The web hook endpoint. This is the URL that GitHub uses to send
    hooks.
    """
    # Ensure that the request is from a GitHub server.
    for network in app.github_networks:
        if request.remote_addr in network:
            break
    else:
        return flask.jsonify(status='you != GitHub'), 403

    # Dispatch based on event type.
    event_type = request.headers.get('X-GitHub-Event')
    if not event_type:
        app.logger.info('Received a non-hook request')
        return flask.jsonify(status='not a hook'), 403
    elif event_type == 'ping':
        return flask.jsonify(status='pong')
    elif event_type == 'push':
        payload = request.get_json()
        repo = payload['repository']

        # If a user whitelist is specified, validate the owner.
        owner = repo['owner']['name']
        name = repo['name']
        allowed_users = app.config['USERS']
        if allowed_users and owner not in allowed_users:
            return flask.jsonify(status='user not allowed', user=owner), 403

        if repo['private']:
            url_format = app.config['PRIVATE_URL_FORMAT']
        else:
            url_format = app.config['PUBLIC_URL_FORMAT']
        app.worker.send(
            app.config['FILENAME_FORMAT'].format(user=owner, repo=name),
            url_format.format(user=owner, repo=name),
        )
        return flask.jsonify(status='handled'), 202
    else:
        return flask.jsonify(status='unhandled event', event=event_type), 501


@app.route('/login')
def login():
    """Redirect to GitHub for authentication."""
    if not app.config['GITHUB_ID']:
        return 'GitHub API disabled', 501
    auth_state = flask.session['auth_state'] = random_string()
    auth_url = '{}?{}'.format(
        'https://github.com/login/oauth/authorize',
        urllib.parse.urlencode({
            'client_id': app.config['GITHUB_ID'],
            'scope': 'write:repo_hook',
            'state': auth_state,
        }),
    )
    app.logger.info(
        'Authorizing with GitHub at {}'.format(auth_url),
    )
    return flask.redirect(auth_url)


@app.route('/auth')
def auth():
    """Receive a callback from GitHub's authentication."""
    if not app.config['GITHUB_ID']:
        return 'GitHub API disabled', 501

    # Get the code from the callback.
    if flask.session.get('auth_state') != request.args['state']:
        app.logger.error(
            'Invalid state from GitHub auth (possible CSRF)'
        )
        return 'invalid request state', 403
    code = request.args['code']

    # Turn this into an access token.
    resp = requests.post(
        'https://github.com/login/oauth/access_token',
        data={
            'client_id': app.config['GITHUB_ID'],
            'client_secret': app.config['GITHUB_SECRET'],
            'code': code,
        }
    )
    token = urllib.parse.parse_qs(resp.text)['access_token'][0]
    app.logger.info(
        'Authorized token with GitHub: {}'.format(token),
    )

    # Check that the user is on the whitelist.
    flask.session['github_token'] = token
    user_data = github_get('user', token=token).json()
    # TODO: Check for organization membership too.
    username = user_data['login']
    if username not in app.config['USERS']:
        app.logger.warn(
            'GitHub user not allowed: {}'.format(username)
        )
        return 'you are not allowed', 403

    # Mark the user as logged in.
    flask.session['github_token'] = token

    return flask.redirect('/')


@app.route('/')
def home():
    token = flask.session.get('github_token')
    if token:
        return 'authorized'
    else:
        return 'not yet'


@app.route('/log/<name>')
def show_log(name):
    token = flask.session.get('github_token')
    if not token:
        return 'no can do', 403
    log_dir = os.path.join(app.config['DATA_DIR'], 'log')
    log_name = os.path.basename(name)  # Avoid any directories in path.
    log_path = os.path.join(log_dir, log_name)
    if not os.path.exists(log_path):
        return 'no such log', 404
    return flask.send_file(log_path, mimetype='text/plain')


@click.command()
@click.option('--host', '-h', default='0.0.0.0', help='server hostname')
@click.option('--port', '-p', default=5000, help='server port')
@click.option('--debug', '-d', is_flag=True, help='run in debug mode')
@click.option('--user', '-u', multiple=True, help='allowed GitHub users')
@click.option('--github', '-g', help='GitHub client id:secret')
@click.option('--secret', '-s', help='application secret key')
def run(host, port, debug, user, github, secret):
    app.config['DEBUG'] = debug
    app.config['USERS'] = user
    if github and ':' in github:
        app.config['GITHUB_ID'], app.config['GITHUB_SECRET'] = \
            github.split(':', 1)
    app.config['SECRET_KEY'] = secret or random_string()
    app.run(host=host, port=port)


if __name__ == '__main__':
    run(auto_envvar_prefix='HOOKNOOK')
