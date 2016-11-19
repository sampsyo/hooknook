# Look! Hooknook.

Hooknook is a preposterously simple tool for deploying code from GitHub. You push to GitHub, Hooknook gets notified via a webhook, and your code does whatever it wants on the server.

You can use it to run "your own GitHub Pages," where every time you push a site's Jekyll source code to GitHub, it automatically gets built and uploaded to a server.

## How to Hooknook

Install it like this:

    $ pip3 install -r requirements.txt

Run it like this:

    $ python3 hooknook.py -u USERNAME

It's a good idea to specify the GitHub users that are allowed to use your server. Otherwise, anyone can look in the Hooknook. The `-u` option can be specified multiple times and also works for organizations. If you don't specify any users, anyone will be allowed. (We filter requests by IP address, so you can't get burned by Hooknook crooks pretending to be GitHub.)

Then, set up a GitHub web hook to point at your server: something like `http://example.com:5000`.

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
* `SECRET_KEY`: A secret string for signing trusted data.
* `PROXIED`: A Boolean indicating whether the application should trust the `X-Forwarded-For` header when determining whether a request came from GitHub.

If you use a config file instead of command-line flags, you can run Hooknook on a proper HTTP server (probably a good idea!). For example, run it with [Gunicorn][] like so:

    $ gunicorn --workers 4 --bind 0.0.0.0:5000 hooknook:app

[Gunicorn]: http://gunicorn.org/

### Running via Launchctl on OSX

Or how to avoid getting rooked running hooknook on your Mac-book (actually, you should probably be running this on a desktop machine, but those don't rhyme).

There are a couple caveats when trying to configure hooknook to run automatically in daemon mode on OSX. Python 3 and Click, which is used by hooknook for parsing configuration options, [do not always play nicely together](http://click.pocoo.org/3/python3/). When running via a launchd script, you need to be sure to set the locale correctly in the environment.

Assuming you've installed python3 the way everyone does (via [homebrew](http://brew.sh)), and that you've cloned hooknook into `/opt/hooknook`, and assuming your user is named "peregrintook" (locally and on Github), your launchd configuration, `/Library/LaunchDaemons/edu.uw.hooknook.plist`, might look like:

    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
      <key>Label</key><string>edu.uw.hooknook</string>
      <key>UserName</key><string>peregrintook</string>
      <key>KeepAlive</key><true/>
      <key>RunAtLoad</key><true/>
      <key>EnvironmentVariables</key>
        <dict>
          <key>LC_ALL</key><string>en_US.UTF-8</string>
          <key>LANG</key><string>en_US.UTF-8</string>
        </dict>
      <key>ProgramArguments</key>
        <array>
          <string>/usr/local/bin/python3</string>
          <string>hooknook.py</string>
          <string>-u</string>
          <string>peregrintook</string>
        </array>
      <key>WorkingDirectory</key><string>/opt/hooknook</string>
      <key>StandardOutPath</key><string>hooknook.log</string>
      <key>StandardErrorPath</key><string>hooknook.log</string>
    </dict>
    </plist>

This daemon can be started with:

    sudo launchctl load /Library/LaunchDaemons/edu.uw.hooknook.plist

