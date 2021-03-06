#!/usr/bin/env python
# coding=utf-8


import unittest

from mock import MagicMock, patch
from click.testing import CliRunner
from collections import deque

from shub import utils
from shub.exceptions import BadParameterException, NotFoundException

from .utils import mock_conf


class UtilsTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_dependency_version_from_setup_is_parsed_properly(self):
        def check(cmd):
            if cmd == 'python setup.py --version':
                return setup_version

        setup_version = ('Building lxml version 3.4.4.'
                         '\nBuilding without Cython.'
                         '\nUsing build configuration of libxslt 1.1.28'
                         '\n3.4.4')

        with self.runner.isolated_filesystem():
            with patch('shub.utils.run', side_effect=check) as mocked_run:
                # given
                mocked_run.return_value = setup_version
                # when
                version = utils._get_dependency_version('lxml')
                # then
                self.assertEquals('lxml-3.4.4', version)

    def test_get_job_specs(self):
        conf = mock_conf(self)

        def _test_specs(job, expected_job_id, expected_endpoint):
            self.assertEqual(
                utils.get_job_specs(job),
                (expected_job_id, conf.get_apikey(expected_endpoint)),
            )
        _test_specs('10/20/30', '10/20/30', 'default')
        _test_specs('2/3', '1/2/3', 'default')
        _test_specs('default/2/3', '1/2/3', 'default')
        _test_specs('prod/2/3', '2/2/3', 'default')
        _test_specs('vagrant/2/3', '3/2/3', 'vagrant')

    def test_get_job_specs_validates_jobid(self):
        invalid_job_ids = ['/1/1', '123', '1/2/a', '1//']
        for job_id in invalid_job_ids:
            with self.assertRaises(BadParameterException):
                utils.get_job_specs(job_id)

    @patch('shub.utils.HubstorageClient', autospec=True)
    def test_get_job(self, mock_HSC):
        class MockJob(object):
            metadata = {'some': 'val'}
        mockjob = MockJob()
        mock_HSC.return_value.get_job.return_value = mockjob
        conf = mock_conf(self)

        self.assertIs(utils.get_job('1/1/1'), mockjob)
        mock_HSC.assert_called_once_with(auth=conf.apikeys['default'])

        with self.assertRaises(BadParameterException):
            utils.get_job('1/1/')

        # Non-existent job
        mockjob.metadata = None
        with self.assertRaises(NotFoundException):
            utils.get_job('1/1/1')

    def test_is_deploy_successful(self):
        # no results
        last_logs = deque(maxlen=5)
        assert not utils._is_deploy_successful(last_logs)
        # missing or incorrect data
        last_logs.append("")
        assert not utils._is_deploy_successful(last_logs)
        last_logs.append("abcdef")
        assert not utils._is_deploy_successful(last_logs)
        last_logs.append('{"field":"wrong"}')
        assert not utils._is_deploy_successful(last_logs)
        # error status
        last_logs.append('{"status":"error"}')
        assert not utils._is_deploy_successful(last_logs)
        # successful status
        last_logs.append('{"status":"ok"}')
        assert utils._is_deploy_successful(last_logs)
        last_logs.append('{"field":"value","status":"ok"}')
        assert utils._is_deploy_successful(last_logs)
        # more complex python expression
        last_logs.append('{"status":"ok", "project": 1111112, '
                         '"version": "1234-master", "spiders": 3}')
        assert utils._is_deploy_successful(last_logs)

    def test_job_live(self):
        job = MagicMock()
        for live_value in ('pending', 'running'):
            job.metadata.__getitem__.return_value = live_value
            self.assertTrue(utils.job_live(job))
        for dead_value in ('finished', 'deleted'):
            job.metadata.__getitem__.return_value = dead_value
            self.assertFalse(utils.job_live(job))

    def test_job_live_updates_metadata(self):
        job = MagicMock(spec=['metadata'])
        with patch('shub.utils.time.time') as mock_time:
            mock_time.return_value = 0
            utils.job_live(job)
            mock_time.return_value = 10
            utils.job_live(job, refresh_meta_after=20)
            self.assertFalse(job.metadata.expire.called)
            utils.job_live(job, refresh_meta_after=5)
            self.assertTrue(job.metadata.expire.called)
            job.metadata.expire.reset_mock()
            utils.job_live(job, refresh_meta_after=5)
            self.assertFalse(job.metadata.expire.called)

    @patch('shub.utils.time.sleep')
    def test_job_resource_iter(self, mock_sleep):
        job = MagicMock(spec=['metadata'])
        job.metadata = {'state': 'running'}

        def magic_iter(*args, **kwargs):
            """
            Return two different iterators on the first two calls, set job's
            state to 'finished' after the second call.
            """
            if magic_iter.stage == 0:
                if 'startafter' in kwargs:
                    self.assertEqual(kwargs['startafter'], None)
                magic_iter.stage = 1
                return iter([1, 2, 3])
            elif magic_iter.stage == 1:
                self.assertEqual(kwargs['startafter'], 456)
                magic_iter.stage = 0
                job.metadata = {'state': 'finished'}
                return iter([4, 5, 6])

        def jri_result(follow):
            return list(utils.job_resource_iter(
                job,
                magic_iter,
                follow,
                key_func=lambda _: 456,
            ))

        magic_iter.stage = 0
        self.assertEqual(jri_result(False), [1, 2, 3])
        self.assertFalse(mock_sleep.called)

        magic_iter.stage = 0
        self.assertEqual(jri_result(True), [1, 2, 3, 4, 5, 6])
        self.assertTrue(mock_sleep.called)

        magic_iter.stage = 0
        job.metadata = {'state': 'finished'}
        self.assertEqual(jri_result(True), [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
