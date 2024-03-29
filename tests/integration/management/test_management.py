# Copyright 2013-2016 DataStax, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
try:
    import unittest2 as unittest
except ImportError:
    import unittest  # noqa

import mock
from cqlmapper import CQLEngineException
from cqlmapper import management
from cqlmapper.management import (
    _get_table_metadata,
    sync_table,
    drop_table,
)
from cqlmapper.models import Model
from cqlmapper import columns

from tests.integration import PROTOCOL_VERSION
from tests.integration.base import BaseCassEngTestCase


class TestModel(Model):

    test_id = columns.Integer(primary_key=True)
    attempt_id = columns.Integer(primary_key=True)
    description = columns.Text()
    expected_result = columns.Integer()
    test_result = columns.Integer()


class KeyspaceManagementTest(BaseCassEngTestCase):
    def test_create_drop_succeeeds(self):
        cluster = self.conn.cluster

        keyspace_ss = 'test_ks_ss'
        self.assertNotIn(keyspace_ss, cluster.metadata.keyspaces)
        management.create_keyspace_simple(self.conn, keyspace_ss, 2)
        self.assertIn(keyspace_ss, cluster.metadata.keyspaces)

        management.drop_keyspace(self.conn, keyspace_ss)
        self.assertNotIn(keyspace_ss, cluster.metadata.keyspaces)

        keyspace_nts = 'test_ks_nts'
        self.assertNotIn(keyspace_nts, cluster.metadata.keyspaces)
        management.create_keyspace_network_topology(
            self.conn,
            keyspace_nts,
            {'dc1': 1},
        )
        self.assertIn(keyspace_nts, cluster.metadata.keyspaces)

        management.drop_keyspace(self.conn, keyspace_nts)
        self.assertNotIn(keyspace_nts, cluster.metadata.keyspaces)


class DropTableTest(BaseCassEngTestCase):

    def test_multiple_deletes_dont_fail(self):
        sync_table(self.conn, TestModel)

        drop_table(self.conn, TestModel)
        drop_table(self.conn, TestModel)


class LowercaseKeyModel(Model):

    first_key = columns.Integer(primary_key=True)
    second_key = columns.Integer(primary_key=True)
    some_data = columns.Text()


class CapitalizedKeyModel(Model):

    firstKey = columns.Integer(primary_key=True)
    secondKey = columns.Integer(primary_key=True)
    someData = columns.Text()


class PrimaryKeysOnlyModel(Model):

    __table_name__ = "primary_keys_only"
    __options__ = {'compaction': {'class': 'LeveledCompactionStrategy'}}

    first_key = columns.Integer(primary_key=True)
    second_key = columns.Integer(primary_key=True)


class PrimaryKeysModelChanged(Model):

    __table_name__ = "primary_keys_only"
    __options__ = {'compaction': {'class': 'LeveledCompactionStrategy'}}

    new_first_key = columns.Integer(primary_key=True)
    second_key = columns.Integer(primary_key=True)


class PrimaryKeysModelTypeChanged(Model):

    __table_name__ = "primary_keys_only"
    __options__ = {'compaction': {'class': 'LeveledCompactionStrategy'}}

    first_key = columns.Float(primary_key=True)
    second_key = columns.Integer(primary_key=True)


class PrimaryKeysRemovedPk(Model):

    __table_name__ = "primary_keys_only"
    __options__ = {'compaction': {'class': 'LeveledCompactionStrategy'}}

    second_key = columns.Integer(primary_key=True)


class PrimaryKeysAddedClusteringKey(Model):

    __table_name__ = "primary_keys_only"
    __options__ = {'compaction': {'class': 'LeveledCompactionStrategy'}}

    new_first_key = columns.Float(primary_key=True)
    second_key = columns.Integer(primary_key=True)


class CapitalizedKeyTest(BaseCassEngTestCase):

    def test_table_definition(self):
        """ Tests that creating a table with capitalized column names succeeds """
        sync_table(self.conn, LowercaseKeyModel)
        sync_table(self.conn, CapitalizedKeyModel)

        drop_table(self.conn, LowercaseKeyModel)
        drop_table(self.conn, CapitalizedKeyModel)


class FirstModel(Model):

    __table_name__ = 'first_model'
    first_key = columns.UUID(primary_key=True)
    second_key = columns.UUID()
    third_key = columns.Text()


class SecondModel(Model):

    __table_name__ = 'first_model'
    first_key = columns.UUID(primary_key=True)
    second_key = columns.UUID()
    third_key = columns.Text()
    fourth_key = columns.Text()


class ThirdModel(Model):

    __table_name__ = 'first_model'
    first_key = columns.UUID(primary_key=True)
    second_key = columns.UUID()
    third_key = columns.Text()
    # removed fourth key, but it should stay in the DB
    blah = columns.Map(columns.Text, columns.Text)


class FourthModel(Model):

    __table_name__ = 'first_model'
    first_key = columns.UUID(primary_key=True)
    second_key = columns.UUID()
    third_key = columns.Text()
    # renamed model field, but map to existing column
    renamed = columns.Map(columns.Text, columns.Text, db_field='blah')


class AddColumnTest(BaseCassEngTestCase):
    def setUp(self):
        super(AddColumnTest, self).setUp()
        drop_table(self.conn, FirstModel)

    def test_add_column(self):
        sync_table(self.conn, FirstModel)
        meta_columns = _get_table_metadata(self.conn, FirstModel).columns
        self.assertEqual(set(meta_columns), set(FirstModel._columns))

        sync_table(self.conn, SecondModel)
        meta_columns = _get_table_metadata(self.conn, FirstModel).columns
        self.assertEqual(set(meta_columns), set(SecondModel._columns))

        sync_table(self.conn, ThirdModel)
        meta_columns = _get_table_metadata(self.conn, FirstModel).columns
        self.assertEqual(len(meta_columns), 5)
        self.assertEqual(len(ThirdModel._columns), 4)
        self.assertIn('fourth_key', meta_columns)
        self.assertNotIn('fourth_key', ThirdModel._columns)
        self.assertIn('blah', ThirdModel._columns)
        self.assertIn('blah', meta_columns)

        sync_table(self.conn, FourthModel)
        meta_columns = _get_table_metadata(self.conn, FirstModel).columns
        self.assertEqual(len(meta_columns), 5)
        self.assertEqual(len(ThirdModel._columns), 4)
        self.assertIn('fourth_key', meta_columns)
        self.assertNotIn('fourth_key', FourthModel._columns)
        self.assertIn('renamed', FourthModel._columns)
        self.assertNotIn('renamed', meta_columns)
        self.assertIn('blah', meta_columns)


class ModelWithTableProperties(Model):

    __options__ = {'bloom_filter_fp_chance': '0.76328',
                   'comment': 'TxfguvBdzwROQALmQBOziRMbkqVGFjqcJfVhwGR',
                   'gc_grace_seconds': '2063',
                   'read_repair_chance': '0.17985',
                   'dclocal_read_repair_chance': '0.50811'}

    key = columns.UUID(primary_key=True)


class TablePropertiesTests(BaseCassEngTestCase):

    def setUp(self):
        super(TablePropertiesTests, self).setUp()
        drop_table(self.conn, ModelWithTableProperties)

    def test_set_table_properties(self):

        sync_table(self.conn, ModelWithTableProperties)
        expected = {
            'bloom_filter_fp_chance': 0.76328,
            'comment': 'TxfguvBdzwROQALmQBOziRMbkqVGFjqcJfVhwGR',
            'gc_grace_seconds': 2063,
            'read_repair_chance': 0.17985,
            # For some reason 'dclocal_read_repair_chance' in CQL is called
            #  just 'local_read_repair_chance' in the schema table.
            #  Source: https://issues.apache.org/jira/browse/CASSANDRA-6717
            #  TODO: due to a bug in the native driver i'm not seeing the
            #  local read repair chance show up
            # 'local_read_repair_chance': 0.50811,
        }
        options = management._get_table_metadata(
            self.conn,
            ModelWithTableProperties,
        ).options
        self.assertEqual(
            dict([(k, options.get(k)) for k in expected.keys()]),
            expected,
        )

    def test_table_property_update(self):
        ModelWithTableProperties.__options__['bloom_filter_fp_chance'] = 0.66778
        ModelWithTableProperties.__options__['comment'] = 'xirAkRWZVVvsmzRvXamiEcQkshkUIDINVJZgLYSdnGHweiBrAiJdLJkVohdRy'
        ModelWithTableProperties.__options__['gc_grace_seconds'] = 96362

        ModelWithTableProperties.__options__['read_repair_chance'] = 0.2989
        ModelWithTableProperties.__options__['dclocal_read_repair_chance'] = 0.12732

        sync_table(self.conn, ModelWithTableProperties)

        table_options = management._get_table_metadata(
            self.conn,
            ModelWithTableProperties,
        ).options

        self.assertDictContainsSubset(
            ModelWithTableProperties.__options__,
            table_options,
        )

    def test_bogus_option_update(self):
        sync_table(self.conn, ModelWithTableProperties)
        option = 'no way will this ever be an option'
        try:
            ModelWithTableProperties.__options__[option] = 'what was I thinking?'
            self.assertRaisesRegexp(
                KeyError,
                "Invalid table option.*%s.*" % option,
                sync_table,
                self.conn,
                ModelWithTableProperties,
            )
        finally:
            ModelWithTableProperties.__options__.pop(option, None)


class SyncTableTests(BaseCassEngTestCase):

    def setUp(self):
        super(SyncTableTests, self).setUp()
        drop_table(self.conn, PrimaryKeysOnlyModel)

    def test_sync_table_works_with_primary_keys_only_tables(self):

        sync_table(self.conn, PrimaryKeysOnlyModel)
        # blows up with DoesNotExist if table does not exist
        table_meta = management._get_table_metadata(
            self.conn,
            PrimaryKeysOnlyModel,
        )

        self.assertIn('LeveledCompactionStrategy', table_meta.as_cql_query())

        PrimaryKeysOnlyModel.__options__['compaction']['class'] = (
            'SizeTieredCompactionStrategy'
        )

        sync_table(self.conn, PrimaryKeysOnlyModel)

        table_meta = management._get_table_metadata(
            self.conn,
            PrimaryKeysOnlyModel,
        )
        self.assertIn(
            'SizeTieredCompactionStrategy',
            table_meta.as_cql_query(),
        )

    def test_primary_key_validation(self):
        """
        Test to ensure that changes to primary keys throw CQLEngineExceptions

        @since 3.2
        @jira_ticket PYTHON-532
        @expected_result Attempts to modify primary keys throw an exception

        @test_category object_mapper
        """
        sync_table(self.conn, PrimaryKeysOnlyModel)
        self.assertRaises(
            CQLEngineException,
            sync_table,
            self.conn,
            PrimaryKeysModelChanged,
        )
        self.assertRaises(
            CQLEngineException,
            sync_table,
            self.conn,
            PrimaryKeysAddedClusteringKey,
        )
        self.assertRaises(
            CQLEngineException,
            sync_table,
            self.conn,
            PrimaryKeysRemovedPk,
        )


class IndexModel(Model):

    __table_name__ = 'index_model'
    first_key = columns.UUID(primary_key=True)
    second_key = columns.Text(index=True)


class IndexCaseSensitiveModel(Model):

    __table_name__ = 'IndexModel'
    __table_name_case_sensitive__ = True
    first_key = columns.UUID(primary_key=True)
    second_key = columns.Text(index=True)


class BaseInconsistent(Model):

    __table_name__ = 'inconsistent'
    first_key = columns.UUID(primary_key=True)
    second_key = columns.Integer(index=True)
    third_key = columns.Integer(index=True)


class ChangedInconsistent(Model):

    __table_name__ = 'inconsistent'
    __table_name_case_sensitive__ = True
    first_key = columns.UUID(primary_key=True)
    second_key = columns.Text(index=True)


class TestIndexSetModel(Model):
    partition = columns.UUID(primary_key=True)
    int_set = columns.Set(columns.Integer, index=True)
    int_list = columns.List(columns.Integer, index=True)
    text_map = columns.Map(columns.Text, columns.DateTime, index=True)
    mixed_tuple = columns.Tuple(columns.Text, columns.Integer, columns.Text, index=True)


class IndexTests(BaseCassEngTestCase):

    def setUp(self):
        super(IndexTests, self).setUp()
        drop_table(self.conn, IndexModel)
        drop_table(self.conn, IndexCaseSensitiveModel)

    def test_sync_index(self):
        """
        Tests the default table creation, and ensures the table_name is
        created and surfaced correctly in the table metadata

        @since 3.1
        @jira_ticket PYTHON-337
        @expected_result table_name is lower case

        @test_category object_mapper
        """
        sync_table(self.conn, IndexModel)
        table_meta = management._get_table_metadata(self.conn, IndexModel)
        self.assertIsNotNone(
            management._get_index_name_by_column(table_meta, 'second_key')
        )

        # index already exists
        sync_table(self.conn, IndexModel)
        table_meta = management._get_table_metadata(self.conn, IndexModel)
        self.assertIsNotNone(
            management._get_index_name_by_column(table_meta, 'second_key')
        )

    def test_sync_index_case_sensitive(self):
        """
        Tests the default table creation, and ensures the table_name is
        created correctly and surfaced correctly in table metadata

        @since 3.1
        @jira_ticket PYTHON-337
        @expected_result table_name is lower case

        @test_category object_mapper
        """
        sync_table(self.conn, IndexCaseSensitiveModel)
        table_meta = management._get_table_metadata(
            self.conn,
            IndexCaseSensitiveModel,
        )
        self.assertIsNotNone(
            management._get_index_name_by_column(table_meta, 'second_key')
        )

        # index already exists
        sync_table(self.conn, IndexCaseSensitiveModel)
        table_meta = management._get_table_metadata(
            self.conn,
            IndexCaseSensitiveModel,
        )
        self.assertIsNotNone(
            management._get_index_name_by_column(table_meta, 'second_key')
        )

    def test_sync_indexed_set(self):
        """
        Tests that models that have container types with indices can be synced.

        @since 3.2
        @jira_ticket PYTHON-533
        @expected_result table_sync should complete without a server error.

        @test_category object_mapper
        """
        sync_table(self.conn, TestIndexSetModel)
        table_meta = management._get_table_metadata(
            self.conn,
            TestIndexSetModel,
        )
        self.assertIsNotNone(
            management._get_index_name_by_column(table_meta, 'int_set')
        )
        self.assertIsNotNone(
            management._get_index_name_by_column(table_meta, 'int_list')
        )
        self.assertIsNotNone(
            management._get_index_name_by_column(table_meta, 'text_map')
        )
        self.assertIsNotNone(
            management._get_index_name_by_column(table_meta, 'mixed_tuple')
        )


class NonModelFailureTest(BaseCassEngTestCase):
    class FakeModel(object):
        pass

    def test_failure(self):
        with self.assertRaises(CQLEngineException):
            sync_table(self.conn, self.FakeModel)


class StaticColumnTests(BaseCassEngTestCase):
    def test_static_columns(self):
        if PROTOCOL_VERSION < 2:
            raise unittest.SkipTest(
                "Native protocol 2+ required, currently using: {0}".format(
                    PROTOCOL_VERSION
                )
            )

        class StaticModel(Model):
            id = columns.Integer(primary_key=True)
            c = columns.Integer(primary_key=True)
            name = columns.Text(static=True)

        drop_table(self.conn, StaticModel)

        session = self.conn.session

        with mock.patch.object(session, "execute", wraps=session.execute) as m:
            sync_table(self.conn, StaticModel)

        self.assertGreater(m.call_count, 0)
        statement = m.call_args[0][0].query_string
        self.assertIn('"name" text static', statement)

        # if we sync again, we should not apply an alter w/ a static
        sync_table(self.conn, StaticModel)

        with mock.patch.object(session, "execute", wraps=session.execute) as m2:
            sync_table(self.conn, StaticModel)

        self.assertEqual(len(m2.call_args_list), 0)
