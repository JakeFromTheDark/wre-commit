# Wrapper for https://pre-commit.com, so `wre-commit`

## Extensions
* Run `pre-commit`:
  * in Docker container when `### wre-commit-docker-image: ...` is found
    in the config file
  * or directly calling locally installed `pre-commit`
* Support multiple configurations using:
  * multiple config files using shell wildcards in option `--config`,
    by default `.pre-commit-config*.yaml`, with respecting the `fail_fast`
    config setting.
  * multi-doc YAML config files, with respecting the `fail_fast` config
    setting.

## Installation into system
Install the wraper by command:
```bash
pip3 install wre-commit
```

## Installation into Git repository
Install this script as `.git/hooks/pre-commit` into your Git repository
by running the command:
```bash
wre-commit install
```
Add option -`t` or `--hook-type` to specify another/more hook(s) to install.

## Uninstallation from Git repository
Uninstall this script as `.git/hooks/pre-commit` from your Git repository
by running the command
```bash
wre-commit uninstall
```
Add option `-t` or `--hook-type` to specify another/more hook(s) to uninstall.

## Usage
Place the line `### wre-commit-docker-image: DOCKER_IMAGE` (without quotes)
into your `pre-commit` config file, typically `.pre-commit-config.yaml`.
Replace the `DOCKER_IMAGE` with the Docker image name in format expected by command `docker run`. That image should have `pre-commit` installed, possibly with other binaries and hook repository dependencies. Then `pre-commit` in that
container will be triggered with your repository dir read-write visible.

You can also call the `pre-commit` in the Docker container directly,
f.e.:
```bash
wre-commit run --all-files
```

If no such line is present in the `pre-commit` config file, then the locally
installed '`re-commit` will be called as usuall.

## Debugging
Set environment variable `WRE_COMMIT_DEBUG` to see debug messages on standard error:
* of the executed commands
* about splitting multi-doc config files

# Requirements
* python3
AND:
  * locally installed and running `docker`
  OR:
  * locally installed `pre-commit`
