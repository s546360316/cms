#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""A script to interact with RWSs using HTTP requests

Provide a handy command-line interface to do common operations on
entities stored on RankingWebServers. Particularly useful to delete an
entity that has been deleted in the DB without any downtime.

"""

from __future__ import unicode_literals

import sys
import argparse

import six

if six.PY3:
    from urllib.parse import quote, urlunsplit
else:
    from urllib import quote
    from urlparse import urlunsplit

from six.moves import xrange

from requests import Session, Request
from requests.exceptions import RequestException

from cms import config, logger


ACTION_METHODS = {
    'get': 'GET',
    'create': 'POST',
    'update': 'PUT',
    'delete': 'DELETE',
    }

ENTITY_TYPES = ['contest',
                'task',
                'team',
                'user',
                'submission',
                'subchange',
                ]


def get_parameters(ranking_shard, entity_type, entity_id):
    protocol, hostname, port = config.rankings_address[ranking_shard]
    username = config.rankings_username[ranking_shard]
    password = config.rankings_password[ranking_shard]

    return (urlunsplit((protocol, '%s:%d' % (hostname, port),
                        '/%ss/%s' % (entity_type, entity_id), '', '')),
            username, password)


def main():
    parser = argparse.ArgumentParser(prog='cmsRWSHelper')
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help="tell on stderr what's happening")
    # FIXME It would be nice to use '--rankings' with action='store'
    # and nargs='+' but it doesn't seem to work with subparsers...
    parser.add_argument(
        '-r', '--ranking', dest='rankings', action='append', default=None,
        choices=list(xrange(len(config.rankings_address))), metavar='shard',
        type=int, help="select which RWS to connect to (omit for 'all')")
    subparsers = parser.add_subparsers(
        title='available actions', metavar='action',
        help='what to ask the RWS to do with the entity')

    # Create the parser for the "get" command
    parser_get = subparsers.add_parser('get', help="retrieve the entity")
    parser_get.set_defaults(action='get')

    # Create the parser for the "create" command
    parser_create = subparsers.add_parser('create', help="create the entity")
    parser_create.set_defaults(action='create')
    parser_create.add_argument(
        'file', type=argparse.FileType('rb'),
        help="file holding the entity body to send ('-' for stdin)")

    # Create the parser for the "update" command
    parser_update = subparsers.add_parser('update', help='update the entity')
    parser_update.set_defaults(action='update')
    parser_update.add_argument(
        'file', type=argparse.FileType('rb'),
        help="file holding the entity body to send ('-' for stdin)")

    # Create the parser for the "delete" command
    parser_delete = subparsers.add_parser('delete', help='delete the entity')
    parser_delete.set_defaults(action='delete')

    # Create the group for entity-related arguments
    group = parser.add_argument_group(
        title='entity reference')
    group.add_argument(
        'entity_type', action='store', choices=ENTITY_TYPES, metavar='type',
        help="type of the entity (e.g. contest, user, task, etc.)")
    group.add_argument(
        'entity_id', action='store', type=six.text_type, metavar='id',
        help='ID of the entity (usually a short codename)')

    # Parse the given arguments
    args = parser.parse_args()

    args.entity_id = quote(args.entity_id)

    if args.verbose:
        verb = args.action[:4] + 'ting'
        logger.info("%s entity '%ss/%s'" % (verb.capitalize(),
                                            args.entity_type, args.entity_id))

    if args.rankings is not None:
        shards = args.rankings
    else:
        shards = list(xrange(len(config.rankings_address)))

    s = Session()
    error = False

    for shard in shards:
        url, username, password = get_parameters(
            shard, args.entity_type, args.entity_id)

        if args.verbose:
            logger.info(
                "Preparing %s request to %s (username: %s; password: %s)" %
                (ACTION_METHODS[args.action], url, username, password))

        req = Request(ACTION_METHODS[args.action],
                      url, auth=(username, password)).prepare()

        if hasattr(args, 'file'):
            if args.verbose:
                logger.info("Reading file contents to use as message body")
            req.body = args.file.read()

        if args.verbose:
            logger.info("Sending request")

        try:
            res = s.send(req, verify=config.https_certfile)
        except RequestException as e:
            logger.error("Failed")
            logger.info(repr(e))
            error = True
            continue

        if args.verbose:
            logger.info("Response received")

        if res.status_code != (201 if args.action == "create" else 200):
            logger.error("Unexpected status code: %d" % res.status_code)
            error = True
            continue

        if args.action == "get":
            print(res.content)

    if error:
        sys.exit(1)


if __name__ == "__main__":
    main()
