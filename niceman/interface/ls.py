# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil; coding: utf-8 -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the niceman package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Helper utility to list available environments
"""

__docformat__ = 'restructuredtext'

from six.moves.configparser import NoSectionError

from pyout import Tabular

from .base import Interface
import niceman.interface.base # Needed for test patching
from ..support.param import Parameter
from ..support.constraints import EnsureStr, EnsureNone
from  ..resource import get_manager
from ..ui import ui
from ..support.exceptions import ResourceError
from ..support.exceptions import ResourceNotFoundError
from ..dochelpers import exc_str

from logging import getLogger
lgr = getLogger('niceman.api.ls')


def _get_status(resource, refresh):
    try:
        if refresh:
            resource.connect()
        if not resource.id:
            # continue  # A missing ID indicates a deleted resource.
            resource.id = 'DELETED'
            resource.status = 'N/A'
        report_status = resource.status
    except Exception as exc:
        lgr.log(5, "%s resource query error: %s", resource.name, exc_str(exc))
        report_status = "N/A (QUERY-ERROR)"
        for f in 'id', 'status':
            if not getattr(resource, f):
                setattr(resource, f, "?")
    return report_status


class Ls(Interface):
    """List known computation resources, images and environments

    Examples
    --------

      $ niceman ls
    """

    _params_ = dict(
        verbose=Parameter(
            args=("-v", "--verbose"),
            action="store_true",
            #constraints=EnsureBool() | EnsureNone(),
            doc="provide more verbose listing",
        ),
        refresh=Parameter(
            args=("--refresh",),
            action="store_true",
            doc="Refresh the status of the resources listed",
            # metavar='CONFIG',
            # constraints=EnsureStr(),
        ),
    )

    @staticmethod
    def __call__(verbose=False, refresh=False):
        if refresh:
            # If refreshing, query status asynchronously.
            def status_fn(resource):
                def fn():
                    return _get_status(resource, True)
                return fn
        else:
            def status_fn(resource):
                return _get_status(resource, False)

        manager = get_manager()

        out = Tabular(
            ["name", "type", "id", "status"],
            style={
                "header_": {"underline": True,
                            "transform": str.upper},
                "status": {"color":
                           {"lookup": {"running": "green",
                                       "stopped": "red",
                                       "N/A (QUERY-ERROR)": "red"}},
                           "bold":
                           {"lookup": {"N/A (QUERY-ERROR)": "red"}}}})

        with out:
            for name in sorted(manager):
                if name.startswith('_'):
                    continue

                try:
                    resource = manager.get_resource(name, resref_type="name")
                except ResourceNotFoundError:
                    lgr.warning("Manager did not return a resource for %r",
                                name)
                    continue

                out([name,
                     resource.type,
                     resource.id,
                     status_fn(resource)])

        # if not refresh:
        #     ui.message('(Use --refresh option to view current status.)')
        #
        # if refresh:
        #     niceman.interface.base.set_resource_inventory(inventory)
