#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from unittest.mock import patch

from fbpcs.infra.logging_service.download_logs.download_logs import AwsContainerLogs


class TestDownloadLogs(unittest.TestCase):
    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_get_cloudwatch_logs(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        aws_container_logs.cloudwatch_client.get_log_events.side_effect = [
            {"events": [{"message": "123"}], "nextForwardToken": "1"},
            {"events": [{"message": "456"}], "nextForwardToken": "2"},
            {"events": [{"message": "789"}], "nextForwardToken": "3"},
            # Repeated event indicates no more data available
            {"events": [{"message": "789"}], "nextForwardToken": "3"},
        ]

        expected = ["123", "456", "789"]
        self.assertEqual(
            expected,
            aws_container_logs.get_cloudwatch_logs("foo", "bar"),
        )
        # NOTE: we don't want to get *too* specific with these asserts
        # because we want to allow the internal details to change and
        # still meet the API requirements
        aws_container_logs.cloudwatch_client.get_log_events.assert_called()

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_parse_container_arn(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_parse_log_events(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_get_container_name_id(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_verify_log_group(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_verify_log_stream(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_create_s3_folder(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_ensure_folder_exists(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_get_s3_folder_contents(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_get_s3_folder_path(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_get_files_to_download_logs(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_download_logs(self, mock_boto3) -> None:
        pass

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_upload_logs_to_s3_from_cloudwatch(self, mock_boto3) -> None:
        pass
