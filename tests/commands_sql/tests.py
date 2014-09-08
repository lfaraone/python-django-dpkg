from __future__ import unicode_literals

import re

from django.apps import apps
from django.core.management.color import no_style
from django.core.management.sql import (sql_create, sql_delete, sql_indexes,
    sql_destroy_indexes, sql_all)
from django.db import connections, DEFAULT_DB_ALIAS, router
from django.test import TestCase
from django.utils import six

# See also initial_sql_regress for 'custom_sql_for_model' tests


class SQLCommandsTestCase(TestCase):
    """Tests for several functions in django/core/management/sql.py"""
    def count_ddl(self, output, cmd):
        return len([o for o in output if o.startswith(cmd)])

    def test_sql_create(self):
        app_config = apps.get_app_config('commands_sql')
        output = sql_create(app_config, no_style(), connections[DEFAULT_DB_ALIAS])

        tables = set()
        create_table_re = re.compile(r'^create table .(?P<table>[\w_]+).*', re.IGNORECASE)
        reference_re = re.compile(r'.* references .(?P<table>[\w_]+).*', re.IGNORECASE)
        for statement in output:
            create_table = create_table_re.match(statement)
            if create_table:
                # Lower since Oracle's table names are upper cased.
                tables.add(create_table.group('table').lower())
                continue
            reference = reference_re.match(statement)
            if reference:
                # Lower since Oracle's table names are upper cased.
                table = reference.group('table').lower()
                self.assertIn(
                    table, tables, "The table %s is referenced before its creation." % table
                )

        self.assertEqual(tables, {
            'commands_sql_comment', 'commands_sql_book', 'commands_sql_book_comments'
        })

    def test_sql_delete(self):
        app_config = apps.get_app_config('commands_sql')
        output = sql_delete(app_config, no_style(), connections[DEFAULT_DB_ALIAS], close_connection=False)
        drop_tables = [o for o in output if o.startswith('DROP TABLE')]
        self.assertEqual(len(drop_tables), 3)
        # Lower so that Oracle's upper case tbl names wont break
        sql = drop_tables[-1].lower()
        six.assertRegex(self, sql, r'^drop table .commands_sql_comment.*')

    def test_sql_indexes(self):
        app_config = apps.get_app_config('commands_sql')
        output = sql_indexes(app_config, no_style(), connections[DEFAULT_DB_ALIAS])
        # PostgreSQL creates one additional index for CharField
        self.assertIn(self.count_ddl(output, 'CREATE INDEX'), [3, 4])

    def test_sql_destroy_indexes(self):
        app_config = apps.get_app_config('commands_sql')
        output = sql_destroy_indexes(app_config, no_style(), connections[DEFAULT_DB_ALIAS])
        # PostgreSQL creates one additional index for CharField
        self.assertIn(self.count_ddl(output, 'DROP INDEX'), [3, 4])

    def test_sql_all(self):
        app_config = apps.get_app_config('commands_sql')
        output = sql_all(app_config, no_style(), connections[DEFAULT_DB_ALIAS])

        self.assertEqual(self.count_ddl(output, 'CREATE TABLE'), 3)
        # PostgreSQL creates one additional index for CharField
        self.assertIn(self.count_ddl(output, 'CREATE INDEX'), [3, 4])


class TestRouter(object):
    def allow_migrate(self, db, model):
        return False


class SQLCommandsRouterTestCase(TestCase):
    def setUp(self):
        self._old_routers = router.routers
        router.routers = [TestRouter()]

    def tearDown(self):
        router.routers = self._old_routers

    def test_router_honored(self):
        app_config = apps.get_app_config('commands_sql')
        for sql_command in (sql_all, sql_create, sql_delete, sql_indexes, sql_destroy_indexes):
            if sql_command is sql_delete:
                output = sql_command(app_config, no_style(), connections[DEFAULT_DB_ALIAS], close_connection=False)
            else:
                output = sql_command(app_config, no_style(), connections[DEFAULT_DB_ALIAS])
            self.assertEqual(len(output), 0,
                "%s command is not honoring routers" % sql_command.__name__)
