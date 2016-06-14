# Copyright 2015 kornicameister@gmail.com
# Copyright 2016 FUJITSU LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime
import random
import ujson
import unittest

from falcon import testing
import mock

from monasca_log_api.reference.common import log_publisher
from monasca_log_api.tests import base

EPOCH_START = datetime.datetime(1970, 1, 1)


class TestSendMessage(testing.TestBase):
    def setUp(self):
        self.conf = base.mock_config(self)
        return super(TestSendMessage, self).setUp()

    @mock.patch('monasca_log_api.reference.common.log_publisher.producer'
                '.KafkaProducer')
    def test_should_not_send_empty_message(self, _):
        instance = log_publisher.LogPublisher()

        instance._kafka_publisher = mock.Mock()
        instance.send_message({})

        self.assertFalse(instance._kafka_publisher.publish.called)

    @unittest.expectedFailure
    def test_should_not_send_message_not_dict(self):
        instance = log_publisher.LogPublisher()
        not_dict_value = 123
        instance.send_message(not_dict_value)

    @mock.patch('monasca_log_api.reference.common.log_publisher.producer'
                '.KafkaProducer')
    def test_should_not_send_message_missing_keys(self, _):
        # checks every combination of missing keys
        # test does not rely on those keys having a value or not,
        # it simply assumes that values are set but important
        # message (i.e. envelope) properties are missing entirely
        # that's why there are two loops instead of three

        instance = log_publisher.LogPublisher()
        keys = ['log', 'creation_time', 'meta']

        for key_1 in keys:
            diff = keys[:]
            diff.remove(key_1)
            for key_2 in diff:
                message = {
                    key_1: random.randint(10, 20),
                    key_2: random.randint(30, 50)
                }
                self.assertRaises(log_publisher.InvalidMessageException,
                                  instance.send_message,
                                  message)

    @mock.patch('monasca_log_api.reference.common.log_publisher.producer'
                '.KafkaProducer')
    def test_should_not_send_message_missing_values(self, _):
        # original message assumes that every property has value
        # test modify each property one by one by removing that value
        # (i.e. creating false-like value)
        instance = log_publisher.LogPublisher()
        message = {
            'log': {
                'message': '11'
            },
            'creation_time': 123456,
            'meta': {
                'region': 'pl'
            }
        }

        for key in message:
            tmp_message = message
            tmp_message[key] = None
            self.assertRaises(log_publisher.InvalidMessageException,
                              instance.send_message,
                              tmp_message)

    @mock.patch('monasca_log_api.reference.common.log_publisher.producer'
                '.KafkaProducer')
    def test_should_send_message(self, kafka_producer):
        instance = log_publisher.LogPublisher()
        instance._kafka_publisher = kafka_producer
        instance.send_message({})

        creation_time = ((datetime.datetime.utcnow() - EPOCH_START)
                         .total_seconds())
        application_type = 'monasca-log-api'
        dimension_1_name = 'disk_usage'
        dimension_1_value = '50'
        dimension_2_name = 'cpu_time'
        dimension_2_value = '60'
        msg = {
            'log': {
                'message': 1,
                'application_type': application_type,
                'dimensions': {
                    dimension_1_name: dimension_1_value,
                    dimension_2_name: dimension_2_value
                }
            },
            'creation_time': creation_time,
            'meta': {
                'tenantId': 1
            }
        }

        instance.send_message(msg)

        instance._kafka_publisher.publish.assert_called_once_with(
            self.conf.conf.log_publisher.topics[0],
            [ujson.dumps(msg)])

    @mock.patch('monasca_log_api.reference.common.log_publisher.producer'
                '.KafkaProducer')
    def test_should_send_message_multiple_topics(self, _):
        topics = ['logs', 'analyzer', 'tester']
        self.conf.config(topics=topics, group='log_publisher')
        self.conf.config(max_log_size=5000, group='service')

        instance = log_publisher.LogPublisher()
        instance._kafka_publisher = mock.Mock()
        instance.send_message({})

        creation_time = ((datetime.datetime.utcnow() - EPOCH_START)
                         .total_seconds())
        dimension_1_name = 'disk_usage'
        dimension_1_value = '50'
        dimension_2_name = 'cpu_time'
        dimension_2_value = '60'
        application_type = 'monasca-log-api'
        msg = {
            'log': {
                'message': 1,
                'application_type': application_type,
                'dimensions': {
                    dimension_1_name: dimension_1_value,
                    dimension_2_name: dimension_2_value
                }
            },
            'creation_time': creation_time,
            'meta': {
                'tenantId': 1
            }
        }
        json_msg = ujson.dumps(msg)

        instance.send_message(msg)

        self.assertEqual(len(topics),
                         instance._kafka_publisher.publish.call_count)
        for topic in topics:
            instance._kafka_publisher.publish.assert_any_call(
                topic,
                [json_msg])

    @mock.patch(
        'monasca_log_api.reference.common.log_publisher.producer'
        '.KafkaProducer')
    def test_should_set_multiple_msgs_to_multiple_topics_diff_keys(self,
                                                                   publisher):
        topics = ['logs', 'analyzer', 'tester']
        self.conf.config(topics=topics, group='log_publisher')
        self.conf.config(max_log_size=5000, group='service')

        instance = log_publisher.LogPublisher()
        instance._kafka_publisher = publisher

        num_of_msgs = 3
        msgs_data = []
        creation_time = ((datetime.datetime.utcnow() - EPOCH_START)
                         .total_seconds())
        for it in xrange(num_of_msgs):
            msg = {
                'log': {
                    'message': it,
                    'dimensions': {
                        'hostname': 'localhost',
                        'component': 'some_component.%d' % it,
                        'path': '/var/log/test/%s/me.log' % it
                    }
                },
                'creation_time': creation_time,
                'meta': {
                    'tenantId': 1
                }
            }
            msgs_data.append(msg)

        instance.send_message(msgs_data)

        self.assertEqual(len(topics),
                         instance._kafka_publisher.publish.call_count)

    @mock.patch(
        'monasca_log_api.reference.common.log_publisher.producer'
        '.KafkaProducer')
    def test_should_set_multiple_msgs_to_multiple_topics_same_keys(self,
                                                                   publisher):
        topics = ['logs', 'analyzer', 'tester']
        self.conf.config(topics=topics, group='log_publisher')
        self.conf.config(max_log_size=5000, group='service')

        instance = log_publisher.LogPublisher()
        instance._kafka_publisher = publisher

        num_of_msgs = 3
        msgs_data = []
        creation_time = ((datetime.datetime.utcnow() - EPOCH_START)
                         .total_seconds())
        for it in xrange(num_of_msgs):
            msg = {
                'log': {
                    'message': it,
                    'application_type': 'some_app_type',
                    'dimensions': {
                        'hostname': 'localhost',
                        'path': '/var/log/test/same_key/me.log'
                    }
                },
                'creation_time': creation_time,
                'meta': {
                    'tenantId': 1
                }
            }
            msgs_data.append(msg)

        instance.send_message(msgs_data)

        self.assertEqual(len(topics),
                         instance._kafka_publisher.publish.call_count)

    @mock.patch(
        'monasca_log_api.reference.common.log_publisher.producer'
        '.KafkaProducer')
    def test_should_set_multiple_msgs_to_single_topic_diff_keys(self,
                                                                publisher):
        topics = ['logs']
        self.conf.config(topics=topics, group='log_publisher')
        self.conf.config(max_log_size=5000, group='service')

        instance = log_publisher.LogPublisher()
        instance._kafka_publisher = publisher

        num_of_msgs = 3
        msgs_data = []
        creation_time = ((datetime.datetime.utcnow() - EPOCH_START)
                         .total_seconds())
        for it in xrange(num_of_msgs):
            msg = {
                'log': {
                    'message': it,
                    'dimensions': {
                        'hostname': 'localhost',
                        'component': 'some_app_type.%d' % it,
                        'path': '/var/log/test/%s/me.log' % it
                    }
                },
                'creation_time': creation_time,
                'meta': {
                    'tenantId': 1
                }
            }
            msgs_data.append(msg)

        instance.send_message(msgs_data)

        self.assertEqual(len(topics),
                         instance._kafka_publisher.publish.call_count)
