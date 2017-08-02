# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the niceman package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Orchestrator sub-class to provide management of the localhost environment."""
import json
import os

import attr
import yaml

from niceman.distributions import Distribution

from .base import SpecObject
from .base import DistributionTracer
from .base import Package
from .base import TypedList
from niceman.dochelpers import exc_str

import logging
lgr = logging.getLogger('niceman.distributions.conda')


@attr.s
class CondaPackage(Package):
    name = attr.ib()
    files = attr.ib(default=attr.Factory(list))


# ~/anaconda
#
# ~/anaconda3
@attr.s
class CondaDistribution(Distribution):
    """
    Class to provide Conda package management.
    """

    path = attr.ib(default=None)
    packages = TypedList(CondaPackage)
    channels = attr.ib(default=None)

    def initiate(self, environment):
        """
        Perform any initialization commands needed in the environment.

        Parameters
        ----------
        environment : object
            The Environment sub-class object.
        """
        return

    def install_packages(self, session=None):
        """
        Install the packages associated to this distribution by the provenance
        into the environment environment.

        Parameters
        ----------
        session : object
            Environment sub-class instance.
        """

        # TODO: Need to figure out a graceful way to install conda before we can install packages here.
        # for package in self.provenance['packages']:
        #     session.add_command(['conda',
        #                            'install',
        #                            package['name']])
        return


class CondaTracer(DistributionTracer):
    """conda distributions tracer
    """

    def _init(self):
        self._paths_cache = {}      # path -> False or CondaDistribution

    def _get_packagefields_for_files(self, files):
        raise NotImplementedError("TODO")

    def _create_package(self, *fields):
        raise NotImplementedError("TODO")

    def _get_conda_meta_files(self, conda_path):
        try:
            out, _ = self._session.run(
                'ls %s/conda-meta/*.json'
                % conda_path,
                expect_fail=True
            )
            return iter(out.splitlines())
        except Exception as exc:
            lgr.warning("Could not retrieve conda-meta files in path %s: %s",
                        conda_path, exc_str(exc))

    def _get_conda_package_details(self, conda_path):
        # TODO: Get details for pip installed packages
        packages = {}
        file_to_package_map = {}
        for meta_file in self._get_conda_meta_files(conda_path):
            try:
                out, err = self._session.run(
                    'cat %s' % meta_file,
                    expect_fail=True
                )
                details = json.loads(out)
#                print meta_file
#                print(json.dumps(details, indent=4))
                if "name" in details:
                    lgr.debug("Found conda package %s", details["name"])
                    # Packages are recorded in the conda environment as
                    # name=version=build
                    conda_package_name = \
                        ("%s=%s=%s" % (details["name"], details["version"],
                                       details["build"]))
                    packages[conda_package_name] = details
                    # Now map the package files to the package
                    for f in details["files"]:
                        full_path = os.path.normpath(
                            os.path.join(conda_path, f))
                        file_to_package_map[full_path] = conda_package_name;
            except Exception as exc:
                lgr.warning("Could not retrieve conda info in path %s: %s",
                            conda_path,
                            exc_str(exc))

        return packages, file_to_package_map

    def _get_conda_env_export(self, root_prefix, conda_path):
        export = {}
        try:
            # NOTE: We need to call conda-env directly.  Conda has problems
            # calling conda-env without a PATH being set...
            out, err = self._session.run(
                '%s/bin/conda-env export -p %s'
                % (root_prefix, conda_path),
                expect_fail=True
            )
            export = yaml.load(out)
        except Exception as exc:
            lgr.warning("Could not retrieve conda environment "
                        "export from path %s: %s", conda_path,
                        exc_str(exc))
        return export

    def _get_conda_info(self, conda_path):
        details = {}
        try:
            out, err = self._session.run(
                '%s/bin/conda info --json'
                % conda_path,
                expect_fail=True
            )
            details = json.loads(out)
        except Exception as exc:
            lgr.warning("Could not retrieve conda info in path %s: %s",
                        conda_path, exc_str(exc))
        return details

    def _get_conda_path(self, path):
        paths = []
        conda_path = None
        while path not in {None, os.path.pathsep, '', '/'}:
            if path in self._paths_cache:
                conda_path = self._paths_cache[path]
                break
            paths.append(path)
            try:
                _, _ = self._session.run(
                    'ls -ld %s/bin/conda %s/conda-meta'
                    % (path, path),
                    expect_fail=True
                )
            except Exception as exc:
                lgr.debug("Did not detect conda at the path %s: %s", path,
                          exc_str(exc))
                path = os.path.dirname(path)  # go to the parent
                continue

            conda_path = path
            lgr.info("Detected conda %s", conda_path)
            break

        for path in paths:
            self._paths_cache[path] = conda_path

        return conda_path

    def identify_distributions(self, paths):
        conda_paths = set()
        # Start with all paths being set as unknown
        unknown_files = set(paths)

        # First, loop through all the files and identify conda paths
        for path in paths:
            conda_path = self._get_conda_path(path)
            if conda_path:
                if conda_path not in conda_paths:
                    conda_paths.add(conda_path)

        # Loop through conda_paths, find packages and create the
        # distributions
        for idx, conda_path in enumerate(conda_paths):

            # Give the distribution a name
            if (len(conda_paths)) > 1:
                dist_name = 'conda-%d' % idx
            else:
                dist_name = 'conda'

            # Retrieve distribution details
            conda_info = self._get_conda_info(conda_path)
            # TODO: Use env_export to get pip packages
            env_export = self._get_conda_env_export(
               conda_info["root_prefix"], conda_path)
            (conda_package_details, file_to_package) = \
                self._get_conda_package_details(conda_path)

            # Loop through packages, initializing a list of found files
            package_to_found_files = {}
            for package_name in conda_package_details:
                package_to_found_files[package_name] = []

            # Loop through unknown files, assigning them to packages if found
            for path in set(unknown_files):  # Clone the set
                if path in file_to_package:
                    # The file was found so remove from unknown file set
                    unknown_files.remove(path)
                    # And add to the package
                    package_to_found_files[file_to_package[path]].append(path)

            packages = []
            # Create the packages
            for package_name in conda_package_details:
                # Skip the package if no files are associated with it
                if not package_to_found_files[package_name]:
                    continue
                # Create the package
                package = CondaPackage(
                    name=package_name,  # TODO: Name, version, and build
                    files=package_to_found_files[package_name]
                )
                packages.append(package)

            # Create the distribution
            dist = CondaDistribution(
                name=dist_name,
                path=conda_path,
                packages=packages
                # TODO: all the packages and paths
            )
            yield dist, list(unknown_files)

