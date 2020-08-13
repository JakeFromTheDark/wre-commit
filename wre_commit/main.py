#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper for https://pre-commit.com, so 'wre-commit'."""

import glob
import logging
import os
import re
import subprocess
import sys
import tempfile


class Program():
    """Program options, arguments, help and version."""

    NAME = "wre-commit"
    VERSION = "1.0.5"

    def __init__(self):

        # set logging
        logging.basicConfig(
            format="%(levelname)s: {}: %(message)s".format(self.NAME),
            level="DEBUG" if "WRE_COMMIT_DEBUG" in os.environ else "INFO",
        )

        # get program name, options and arguments
        self.name = os.path.basename(sys.argv[0])
        self.args = []
        self.opts = sys.argv[1:]

        try:
            index = self.opts.index("--")
            self.args = self.opts[index:]
            self.opts = self.opts[:index]
        except ValueError:
            pass

    def print_help(self):
        """Print help."""
        print(
            """usage: {NAME} [-h] [-V] {{install,uninstall,help,*}} ...

positional arguments:
    install             Install the {NAME} script as a symlink.
    uninstall           Uninstall the {NAME} script.
    help                Show help for a specific command of the {NAME}
                        and the first pre-commit and exit.
    *                   Run pre-commit(s) with the command and agruments.

optional arguments:
  -h, --help            show help message of the {NAME} and the first
                        pre-commit and exit
  -V, --version         show version number of the {NAME} and all
                        pre-commits and exit

""".format(NAME=self.NAME))

    def print_version(self):
        """Print version."""
        print("{} {}".format(self.NAME, self.VERSION))

    def get_command(self):
        """Get command as the first oprion."""
        try:
            return self.opts[0]
        except ValueError:
            return None

    def get_option(self, keys, default=None):
        """Get option of given key(s) optionally with a default."""
        last = len(self.opts) - 1
        for i, opt in enumerate(self.opts):
            if opt in keys and i < last:
                return self.opts[i + 1]
            try:
                (key, value) = opt.split("=", 1)
                if key in keys:
                    return value
            except ValueError:
                pass
        return default

    @classmethod
    def die(cls, msg):
        """Print error message and exit with failure."""
        logging.error(msg)
        sys.exit(1)


class File():
    """Wrap file operation with friendly error messages."""

    # custom exception
    class Error(Exception):
        """Custom exception."""

    @classmethod
    def read(cls, file):
        """Get content of a file."""
        try:
            with open(file) as handler:
                content = handler.read()
        except IOError as exc:
            raise cls.Error("Reading file {}: {}".format(file, exc))
        return content

    @classmethod
    def delete(cls, file):
        """Delete a file."""
        try:
            return os.remove(file)
        except OSError as exc:
            raise cls.Error("Deleting file {}: {}".format(file, exc))

    @classmethod
    def rename(cls, file_from, file_to):
        """Rename a file."""
        try:
            return os.rename(file_from, file_to)
        except OSError as exc:
            raise cls.Error(
                "Renaming file {} to {}: {}".format(file_from, file_to, exc),
            )

    @classmethod
    def symlink(cls, file, symlink):
        """Create a symlink to a file."""
        try:
            return os.symlink(file, symlink)
        except OSError as exc:
            raise cls.Error(
                "Symlinking file {} to {}: {}".format(file, symlink, exc),
            )

    @classmethod
    def chdir(cls, path):
        """Change the current working directory."""
        try:
            os.chdir(path)
        except OSError as exc:
            raise cls.Error("Changing directory to {}: {}".format(path, exc))


class Command():
    """Wrap runningcommands with friendly error messages."""

    # custom exception
    class Error(Exception):
        """Custom exception."""

    # pre-compile regular expressions
    RE_SHEBANG = re.compile(r"^#!(\S+)")

    @classmethod
    def run(cls, *args, chdir=None):
        """Run command with arguments."""
        # change directory?
        if chdir is not None:
            old_dir = os.getcwd()
            File.chdir(chdir)

        # run the command
        try:
            output = subprocess.check_output(
                args, stderr=subprocess.STDOUT
            )  # nosec
        except subprocess.CalledProcessError as exp:
            raise cls.Error(
                "Execution of command `{}` failed: {}".format(args[0], exp),
            )

        # change directory back?
        if chdir is not None:
            File.chdir(old_dir)

        return output.decode()

    @classmethod
    def which(cls, file):
        """Find executable in PATH."""
        for path in os.environ["PATH"].split(os.pathsep):
            executable = os.path.join(path, file)
            if os.path.exists(executable) and os.access(executable, os.X_OK):
                return executable
        raise cls.Error("Executable `{}`: not found".format(file))

    @classmethod
    def shebang(cls, file):
        """Get executable from shebang of a file."""
        try:
            with open(file) as handler:
                shebang = handler.readline()
        except IOError as exc:
            raise cls.Error(
                "Getting shebang from file {}: {}".format(file, exc),
            )

        match = cls.RE_SHEBANG.match(shebang)
        if match:
            return match.group(1)

        raise cls.Error(
            "Getting executable from shebang from file {}: not found".format(
                file,
            ),
        )


class YAML():
    """Handle YAML files."""

    # custom exception
    class Error(Exception):
        """Custom exception."""

    @classmethod
    def get_docs(cls, file, preserve_line_number=True):
        """Split YAML document(s) into arrays of lines."""
        docs = [""]
        try:
            with open(file) as handler:
                for lines, line in enumerate(handler.readlines()):
                    if line.rstrip() == "---" and docs[-1]:
                        docs.append("")
                        if preserve_line_number:
                            docs[-1] += "\n" * lines
                    docs[-1] += line
        except IOError as exc:
            raise cls.Error("Config file {}: {}".format(file, exc))
        return docs


class Hooks():
    """Handle github hooks."""

    # keep that value exactly as is across all the versions
    UNIQUE_SIGNATURE = (
        "from wre_commit.main import main"
    )

    # supported hook types
    SUPPORTED_HOOK_TYPES = [
        "pre-commit",
        "commit-msg",
        "post-checkout",
        "pre-merge-commit",
        "pre-push",
        "prepare-commit-msg",
    ]

    # custom exception
    class Error(Exception):
        """Custom exception."""

    @classmethod
    def _get_git_dir(cls, git_root="."):
        """Get git dir."""
        opts = ("--git-common-dir", "--git-dir")
        output = Command.run("git", "rev-parse", chdir=git_root, *opts)
        for line, opt in zip(output.splitlines(), opts):
            if line != opt:  # pragma: no branch (git < 2.5)
                return os.path.normpath(os.path.join(git_root, line))
        raise Command.Error("No git dir detected")

    @classmethod
    def _is_our_script(cls, file):
        """Is the file our script?"""
        return File.read(file).find(cls.UNIQUE_SIGNATURE) != -1

    @classmethod
    def _split_hook_types(cls, hook_types=None):
        """Split hook types or use defaults."""
        if hook_types is None:
            return cls.SUPPORTED_HOOK_TYPES[0:1]
        return hook_types.split(",")

    @classmethod
    def _hook_paths(cls, hook_type):
        """Get hook paths: the hook and legacy backup."""
        if hook_type not in cls.SUPPORTED_HOOK_TYPES:
            raise cls.Error("Unsupported hook type: {}".format(hook_type))

        # compose and return paths
        path = os.path.join(cls._get_git_dir(), "hooks", hook_type)
        return path, "{}.legacy.{}".format(path, Program.NAME)

    @classmethod
    def install(cls, hook_types=None):
        """Install or the hook(s)."""
        for hook_type in cls._split_hook_types(hook_types):
            hook_path, legacy_hook_path = cls._hook_paths(hook_type)

            # store previous hook?
            if os.path.exists(hook_path) and not cls._is_our_script(hook_path):
                File.rename(hook_path, legacy_hook_path)
                print("Previous hook stored to {}".format(legacy_hook_path))

            # delete old hook
            if os.path.exists(hook_path):
                File.delete(hook_path)

            # install the hook
            File.symlink(Command.which("wre-commit"), hook_path)
            print("{} installed at {}".format(hook_type, hook_path))

        return 0

    @classmethod
    def uninstall(cls, hook_types=None):
        """Uninstall the hook(s)."""
        for hook_type in cls._split_hook_types(hook_types):
            hook_path, legacy_hook_path = cls._hook_paths(hook_type)

            if os.path.exists(hook_path) and cls._is_our_script(hook_path):

                # remove the hook
                File.delete(hook_path)
                print("{} uninstalled".format(hook_type))

                # restore previous hook?
                if os.path.exists(legacy_hook_path):
                    File.rename(legacy_hook_path, hook_path)
                    print("Restored previous hook to {}".format(hook_path))

        return 0


class PreCommit():
    """Run pre-commit."""

    # pre-compile regular expressions
    RE_KEY = re.compile(r"^([^:]+):([^#]+)")

    # is the program called by git?
    CALLED_BY_GIT = "GIT_AUTHOR_DATE" in os.environ

    # the current working directory
    PWD = os.getcwd()

    # config key for the docker image
    KEY_DOCKER_IMAGE = "### {}-docker-image".format(Program.NAME)

    def __init__(self, name, opts, args, command):
        self.name = name
        self.opts = opts
        self.args = args
        self.command = command

    def _compose_command_for_docker(self, docker_image):
        """Compose command for precommit executed in Docker."""

        # initial arguments
        # ... with read-write current dir visible on the same path,
        run_args = [
            "docker",
            "run",
            "-v",
            "{pwd}/:{pwd}/:rw".format(pwd=self.PWD),
            "-w",
            self.PWD,
            docker_image,
            "pre-commit",
        ]

        # ... in interactive mode when not called by `git commit`
        if not self.CALLED_BY_GIT:
            run_args.insert(2, "-it")

        return run_args

    @classmethod
    def _compose_command_for_local(cls):
        """Compose command for locally executed pre-commit."""
        executable = Command.which("pre-commit")
        interpreter = Command.shebang(executable)
        return [interpreter, executable]

    def _compose_args_for_git(self, config_file):
        """Compose arguments when called from git."""
        return [
            "hook-impl",
            "--config",
            config_file,
            "--hook-type",
            self.name,
            "--hook-dir",
            self.PWD,
            "--",
        ]

    def _fix_config_option(self, config_file):
        """Fix config option to the current config file."""
        last = len(self.opts) - 1
        for i, opt in enumerate(self.opts):
            if opt in ("-c", "--config") and i < last:
                self.opts[i + 1] = config_file
                break
            if opt.split("=", 1)[0] in ("-c", "--config"):
                self.opts[i] = opt.split("=", 1)[0] + "=" + config_file
                break
        else:
            if self.command not in ["help"]:
                self.opts.append("--config=" + config_file)

    def run(self, config_file, config_content):
        """Run pre-commit over a single config file."""
        # compose pre-commit execution and arguments
        docker_image = None
        fail_fast = False

        # get docker image and fail fast options from config, if any
        for line in config_content.splitlines():
            match = self.RE_KEY.match(line)
            if match:
                value = match.group(2).strip()
                if match.group(1) == self.KEY_DOCKER_IMAGE:
                    docker_image = value
                elif match.group(1) == "fail_fast" and value == "true":
                    fail_fast = True

        # run in docker?
        if docker_image:
            run_args = self._compose_command_for_docker(docker_image)

        # run locally?
        else:
            run_args = self._compose_command_for_local()

        # called by `git commit`?
        if self.CALLED_BY_GIT:
            run_args.extend(self._compose_args_for_git(config_file))

        # called manually
        else:
            self._fix_config_option(config_file)

        # append program options and arguments
        run_args.extend(self.opts)
        run_args.extend(self.args)

        # run the pre-commit finally
        logging.debug("Executing: %s", " ".join(run_args))
        retcode = subprocess.call(run_args)  # nosec

        return (retcode, fail_fast)


def main():
    """Main function."""
    main_retcode = 0
    run_once = False

    # process program options and arguments
    program = Program()
    command = program.get_command()

    try:

        if command in ["-h", "--help", "help"]:
            program.print_help()
            run_once = True

        elif command in ["-V", "--version"]:
            program.print_version()

        elif command == "install":
            return Hooks.install(
                program.get_option(["-t", "--hook-type"]),
            )

        elif command == "uninstall":
            return Hooks.uninstall(
                program.get_option(["-t", "--hook-type"]),
            )

        # run only once when a help of a command is requested
        if "-h" in program.opts or "--help" in program.opts:
            run_once = True

        # initialize pre-commit
        pre_commit = PreCommit(
            name=program.name,
            opts=program.opts,
            args=program.args,
            command=command,
        )

        # go thru all config files matching option --config
        option_config = program.get_option(
            ["-c", "--config"], default=".pre-commit-config*.yaml",
        )
        for config_file in sorted(glob.glob(option_config)):

            # get all documents of the config file
            docs = YAML.get_docs(config_file)

            # run pre-commit with the original config file?
            if len(docs) == 1:
                (retcode, fail_fast) = pre_commit.run(config_file, docs[0])
                main_retcode = max(main_retcode, retcode)
                if run_once or (retcode and fail_fast):
                    return main_retcode

            # else run pre-commit on split temporary config files
            #  for each document
            else:
                for index, doc in enumerate(docs, 1):
                    with tempfile.NamedTemporaryFile(
                            mode='w',
                            prefix=".pre-commit-config-",
                            suffix=".yaml",
                            dir=os.getcwd(),
                    ) as handler:
                        handler.write(doc)
                        handler.flush()
                        logging.debug(
                            "Extracted %d. document from %s to %s",
                            index, config_file, handler.name
                        )
                        (retcode, fail_fast) = pre_commit.run(
                            handler.name,
                            doc,
                        )
                        main_retcode = max(main_retcode, retcode)
                        if run_once or (retcode and fail_fast):
                            return main_retcode

    except (File.Error, Command.Error, YAML.Error, Hooks.Error) as exc:
        Program.die("Error: {}".format(exc))

    return main_retcode


if __name__ == "__main__":
    sys.exit(main())
