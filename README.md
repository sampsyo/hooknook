# Look! Hooknook.

Hooknook is a preposterously simple tool for deploying code from GitHub. You push to GitHub, Hooknook gets notified via a webhook, and your code does whatever it wants on the server.

You can use it to run "your own GitHub Pages," where every time you push a site's Jekyll source code to GitHub, it automatically gets built and uploaded to a server.

## How to Hooknook

Run it like this:

    $ python3 hooknook.py -u USERNAME

It's a good idea to specify the GitHub users that are allowed to use your server. Otherwise, anyone can look in the Hooknook. The `-u` option can be specified multiple times and also works for organizations. If you don't specify any users, anyone will be allowed. (We filter requests by IP address, so you can't get burned by Hooknook crooks pretending to be GitHub.)

Then, set up a GitHub web hook to point at the `http://example.com/hook` on your server.

Every time you push to your repository, Hooknook will update your repository in `~/.hooknook/repo` and run a command in that directory. By default, the command is `make deploy`, so you can configure your build just by writing a Makefile.

But if you want to run a different command, add a file called `.hook.yaml` to your repo. This is a [YAML][] file that (currently) has only one key: `deploy`, which is a command that tells Hooknook how to cook.

Every hook is logged to a timestamped file in `~/.hooknook/log`. Look in the Hooknook logbook if you think something is going wrong.

[YAML]: https://en.wikipedia.org/wiki/YAML
