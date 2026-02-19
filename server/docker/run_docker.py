# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


# yinying edit this file from deepmind alphafold repo

"""Docker launch script for REvoDesign PSSM_GREMLIN docker image."""

import os
import signal

import docker
from absl import app, flags, logging
from docker import types

flags.DEFINE_string("fasta", None, "Path to a specific FASTA filename.")
flags.DEFINE_integer("nproc", os.cpu_count(), "Number of CPU cores to launch")

flags.DEFINE_string("output", None, "Path to a output file")
flags.DEFINE_string(
    "uniref30_db",
    "/mnt/db/uniref30_uc30/UniRef30_2022_02/UniRef30_2022_02",
    "<uniref30_db> Path/prefix to Uniclust30 database.",
)
flags.DEFINE_string("uniref90_db", "/mnt/db/uniref90/uniref90", "Path/prefix to Uniref90")
flags.DEFINE_boolean("make_uniref90_db", False, "Whether to use `makeblastdb` tool for formatting uniref90 database.")

flags.DEFINE_string("docker_image_name", "revodesign-pssm-gremlin", "Name of the Docker image.")

flags.DEFINE_string(
    "docker_user",
    f"{os.geteuid()}:{os.getegid()}",
    "UID:GID with which to run the Docker container. The output directories "
    "will be owned by this user:group. By default, this is the current user. "
    "Valid options are: uid or uid:gid, non-numeric values are not recognised "
    "by Docker unless that user has been created within the container.",
)

FLAGS = flags.FLAGS

try:
    _ROOT_MOUNT_DIRECTORY = f"/home/{os.getlogin()}"
except BaseException:
    _ROOT_MOUNT_DIRECTORY = os.path.abspath("/tmp/")
    os.makedirs(_ROOT_MOUNT_DIRECTORY, exist_ok=True)


def _create_mount(mount_name: str, path: str, read_only=True) -> tuple[types.Mount, str]:
    """Create a mount point for each file and directory used by the model."""
    path = os.path.abspath(path)
    target_path = os.path.join(_ROOT_MOUNT_DIRECTORY, mount_name)

    if not read_only:
        logging.warning(f"{mount_name} is not read-only!")

    if os.path.isdir(path):
        source_path = path
        mounted_path = target_path
    else:
        source_path = os.path.dirname(path)
        mounted_path = os.path.join(target_path, os.path.basename(path))
    if not os.path.exists(source_path):
        os.makedirs(source_path)
    logging.info("Mounting %s -> %s", source_path, target_path)
    mount = types.Mount(target=str(target_path), source=str(source_path), type="bind", read_only=read_only)
    return mount, str(mounted_path)


def main(argv):
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments.")

    mounts = []
    command_args = []

    if FLAGS.fasta:
        fasta = os.path.abspath(FLAGS.fasta)
        mount_fasta, mounted_fasta = _create_mount(mount_name="fasta", path=fasta, read_only=True)
        mounts.append(mount_fasta)
        command_args.append(f"-i {mounted_fasta}")

    if FLAGS.output:
        os.makedirs(FLAGS.output, exist_ok=True)
        output = os.path.abspath(FLAGS.output)
        mount_output, mounted_output = _create_mount(mount_name="output", path=output, read_only=False)
        mounts.append(mount_output)
        command_args.append(f"-o {mounted_output}")

    if FLAGS.uniref30_db:
        uniref30_db = os.path.abspath(FLAGS.uniref30_db)
        mount_uniref30_db, mounted_uniref30_db = _create_mount(
            mount_name="uniref30_db", path=uniref30_db, read_only=True
        )
        mounts.append(mount_uniref30_db)
        command_args.append(f"-U {mounted_uniref30_db}")

    if FLAGS.uniref90_db:
        uniref90_db = os.path.abspath(FLAGS.uniref90_db)
        mount_uniref90_db, mounted_uniref90_db = _create_mount(
            mount_name="uniref90_db", path=uniref90_db, read_only=not FLAGS.make_uniref90_db
        )
        mounts.append(mount_uniref90_db)
        command_args.append(f"-u {mounted_uniref90_db}")

    command_args.append(f"-j {FLAGS.nproc}")

    logging.info(command_args)

    client = docker.from_env()

    container = client.containers.run(
        image=FLAGS.docker_image_name,
        command=command_args,
        remove=True,
        detach=True,
        mounts=mounts,
        user=FLAGS.docker_user,
    )

    # Add signal handler to ensure CTRL+C also stops the running container.
    signal.signal(signal.SIGINT, lambda unused_sig, unused_frame: container.kill())

    for line in container.logs(stream=True):
        logging.info(line.strip().decode("utf-8"))


if __name__ == "__main__":
    flags.mark_flags_as_required(
        [
            "fasta",
            "output",
        ]
    )
    app.run(main)
