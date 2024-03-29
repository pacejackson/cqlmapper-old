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

from cassandra import InvalidRequest
from cqlmapper.management import sync_table, drop_table
from tests.integration.base import BaseCassEngTestCase
from cqlmapper.models import Model
from uuid import uuid4
from cqlmapper import columns
from cqlmapper.query_set import ModelQuerySet
import mock
from tests.integration import CASSANDRA_VERSION


class TestTTLModel(Model):
    id = columns.UUID(primary_key=True, default=uuid4)
    count = columns.Integer()
    text = columns.Text(required=False)


class BaseTTLTest(BaseCassEngTestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseTTLTest, cls).setUpClass()
        sync_table(cls.connection(), TestTTLModel)

    @classmethod
    def tearDownClass(cls):
        super(BaseTTLTest, cls).tearDownClass()
        drop_table(cls.connection(), TestTTLModel)


class TestDefaultTTLModel(Model):
    __options__ = {'default_time_to_live': 20}
    id = columns.UUID(primary_key=True, default=uuid4)
    count = columns.Integer()
    text = columns.Text(required=False)


class BaseDefaultTTLTest(BaseCassEngTestCase):

    @classmethod
    def setUpClass(cls):
        if CASSANDRA_VERSION >= '2.0':
            super(BaseDefaultTTLTest, cls).setUpClass()
            conn = cls.connection()
            sync_table(conn, TestDefaultTTLModel)
            sync_table(conn, TestTTLModel)

    @classmethod
    def tearDownClass(cls):
        if CASSANDRA_VERSION >= '2.0':
            super(BaseDefaultTTLTest, cls).tearDownClass()
            conn = cls.connection()
            drop_table(conn, TestDefaultTTLModel)
            drop_table(conn, TestTTLModel)


class TTLQueryTests(BaseTTLTest):

    def test_update_queryset_ttl_success_case(self):
        """ tests that ttls on querysets work as expected """

    def test_select_ttl_failure(self):
        """ tests that ttls on select queries raise an exception """


class TTLModelTests(BaseTTLTest):

    def test_ttl_included_on_create(self):
        """ tests that ttls on models work as expected """

        with mock.patch.object(self.conn.session, 'execute') as m:
            TestTTLModel.ttl(60).create(self.conn, text="hello blake")

        query = m.call_args[0][0].query_string
        self.assertIn("USING TTL", query)

    def test_queryset_is_returned_on_class(self):
        """
        ensures we get a queryset descriptor back
        """
        qs = TestTTLModel.ttl(60)
        self.assertTrue(
            isinstance(qs, ModelQuerySet), type(qs)
        )


class TTLInstanceUpdateTest(BaseTTLTest):
    def test_update_includes_ttl(self):
        model = TestTTLModel.create(self.conn, text="goodbye blake")
        with mock.patch.object(self.conn.session, 'execute') as m:
            model.ttl(60).update(self.conn, text="goodbye forever")

        query = m.call_args[0][0].query_string
        self.assertIn("USING TTL", query)

    def test_update_syntax_valid(self):
        # sanity test that ensures the TTL syntax is accepted by cassandra
        model = TestTTLModel.create(self.conn, text="goodbye blake")
        model.ttl(60).update(self.conn, text="goodbye forever")


class TTLInstanceTest(BaseTTLTest):
    def test_instance_is_returned(self):
        """
        ensures that we properly handle the instance.ttl(60).save() scenario
        :return:
        """
        o = TestTTLModel.create(self.conn, text="whatever")
        o.text = "new stuff"
        o = o.ttl(60)
        self.assertEqual(60, o._ttl)

    def test_ttl_is_include_with_query_on_update(self):
        o = TestTTLModel.create(self.conn, text="whatever")
        o.text = "new stuff"
        o = o.ttl(60)

        with mock.patch.object(self.conn.session, 'execute') as m:
            o.save(self.conn)

        query = m.call_args[0][0].query_string
        self.assertIn("USING TTL", query)


class TTLBlindUpdateTest(BaseTTLTest):
    def test_ttl_included_with_blind_update(self):
        o = TestTTLModel.create(self.conn, text="whatever")
        tid = o.id

        with mock.patch.object(self.conn.session, 'execute') as m:
            TestTTLModel.objects(
                id=tid
            ).ttl(60).update(self.conn, text="bacon")

        query = m.call_args[0][0].query_string
        self.assertIn("USING TTL", query)


@unittest.skipIf(
    CASSANDRA_VERSION < '2.0',
    "default_time_to_Live was introduce in C* 2.0, "
    "currently running {0}".format(CASSANDRA_VERSION)
)
class TTLDefaultTest(BaseDefaultTTLTest):
    def get_default_ttl(self, table_name):
        try:
            default_ttl = self.conn.session.execute(
                "SELECT default_time_to_live FROM system_schema.tables "
                "WHERE keyspace_name = 'cqlengine_test' AND "
                "table_name = '{0}'".format(table_name)
            )
        except InvalidRequest:
            default_ttl = self.conn.session.execute(
                "SELECT default_time_to_live "
                "FROM system.schema_columnfamilies "
                "WHERE keyspace_name = 'cqlengine_test' "
                "AND columnfamily_name = '{0}'".format(table_name)
            )
        return default_ttl[0]['default_time_to_live']

    def test_default_ttl_not_set(self):
        o = TestTTLModel.create(self.conn, text="some text")
        tid = o.id

        self.assertIsNone(o._ttl)

        default_ttl = self.get_default_ttl('test_ttlmodel')
        self.assertEqual(default_ttl, 0)

        with mock.patch.object(self.conn.session, 'execute') as m:
            TestTTLModel.objects(id=tid).update(self.conn, text="aligators")

        query = m.call_args[0][0].query_string
        self.assertNotIn("USING TTL", query)

    def test_default_ttl_set(self):
        o = TestDefaultTTLModel.create(self.conn, text="some text on ttl")
        tid = o.id

        # Should not be set, it's handled by Cassandra
        self.assertIsNone(o._ttl)

        default_ttl = self.get_default_ttl('test_default_ttlmodel')
        self.assertEqual(default_ttl, 20)

        with mock.patch.object(self.conn.session, 'execute') as m:
            TestTTLModel.objects(
                id=tid
            ).update(self.conn, text="aligators expired")

        # Should not be set either
        query = m.call_args[0][0].query_string
        self.assertNotIn("USING TTL", query)

    def test_default_ttl_modify(self):
        default_ttl = self.get_default_ttl('test_default_ttlmodel')
        self.assertEqual(default_ttl, 20)

        TestDefaultTTLModel.__options__ = {'default_time_to_live': 10}
        sync_table(self.conn, TestDefaultTTLModel)

        default_ttl = self.get_default_ttl('test_default_ttlmodel')
        self.assertEqual(default_ttl, 10)

        # Restore default TTL
        TestDefaultTTLModel.__options__ = {'default_time_to_live': 20}
        sync_table(self.conn, TestDefaultTTLModel)

    def test_override_default_ttl(self):
        o = TestDefaultTTLModel.create(self.conn, text="some text on ttl")
        tid = o.id

        o.ttl(3600)
        self.assertEqual(o._ttl, 3600)

        with mock.patch.object(self.conn.session, 'execute') as m:
            TestDefaultTTLModel.objects(
                id=tid
            ).ttl(None).update(self.conn, text="aligators expired")

        query = m.call_args[0][0].query_string
        self.assertNotIn("USING TTL", query)
