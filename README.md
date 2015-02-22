# Look! Hooknook.

Hooknook is a preposterously simple tool for deploying code from GitHub. You push to GitHub, Hooknook gets notified via a webhook, and your code does whatever it wants on the server.

You can use it to run "your own GitHub Pages," where every time you push a site's Jekyll source code to GitHub, it automatically gets built and uploaded to a server.

## How to Hooknook

Install it like this:

    $ pip3 install -r requirements.txt

Run it like this:

    $ python3 hooknook.py -u USERNAME

It's a good idea to specify the GitHub users that are allowed to use your server. Otherwise, anyone can look in the Hooknook. The `-u` option can be specified multiple times and also works for organizations. If you don't specify any users, anyone will be allowed. (We filter requests by IP address, so you can't get burned by Hooknook crooks pretending to be GitHub.)

Then, set up a GitHub web hook to point at the `http://example.com:5000/hook` on your server.

Every time you push to your repository, Hooknook will update your repository in `~/.hooknook/repo` and run `make deploy`. Use a Makefile to describe what to do.

## .hook.yaml

If you want to run a different command (i.e., something other than `make deploy`), add a file called `.hook.yaml` to your repo. This is a [YAML][] file that (currently) has only one key: `deploy`, which is a command that tells Hooknook how to cook.

[YAML]: https://en.wikipedia.org/wiki/YAML

## Logs

Every hook is logged to a timestamped file in `~/.hooknook/log`. Look in the Hooknook logbook if you think something is going wrong.

## Web Interface

Hooknook can show you its logs through a Web interface. To keep this secure, it authenticates users with their GitHub credentials.

To make this work, you need to register your Hooknook installation as a GitHub application. Here's how:

1. Go to your GitHub settings and [make a new application][gh-app-new].
2. Fill in the callback URL using `/auth` on your server: like `http://example.com:5000/auth`. Fill in reasonable values for the other fields.
3. Get your "Client ID" and "Client Secret" for the new application from GitHub. Start Hooknook with the `-g ID:SECRET` option. This enables authentication.
4. Head your Hooknook server's home page (e.g., `http://example.com:5000`) and click the login button. Sign in as one of the whitelisted users.

You'll now see a list of the most recent logs on the server.

Currently, all whitelisted users can view all logs. In the future, users will only be able to see logs for repositories they have access to.

[gh-app-new]: https://github.com/settings/applications/new

## Configuration

You can configure Hooknook with command-line flags or a configuration file. Hooknook looks for a (Python) file called `hooknook.cfg` by default, and you can also supply a `HOOKNOOK_CFG` environment variable to point to another path if you like.

The configuration options are:

* `USERS` or `-u USER`: A list of whitelisted GitHub user/organization names.
* `GITHUB_ID` and `GITHUB_SECRET` or `-g ID:SECRET`: GitHub API credentials.
* `SECRET`: A secret string for signing trusted data.
