#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from unittest.mock import patch

from botocore.exceptions import ClientError

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

        ####################
        # Test error cases #
        ####################
        aws_container_logs.cloudwatch_client.get_log_events.reset_mock()
        aws_container_logs.cloudwatch_client.get_log_events.side_effect = ClientError(
            error_response={"Error": {"Code": "InvalidParameterException"}},
            operation_name="get_log_events",
        )
        with self.assertRaisesRegex(Exception, "Couldn't fetch.*"):
            aws_container_logs.get_cloudwatch_logs("foo", "bar")
            aws_container_logs.cloudwatch_client.get_log_events.assert_called()

        aws_container_logs.cloudwatch_client.get_log_events.reset_mock()
        aws_container_logs.cloudwatch_client.get_log_events.side_effect = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException"}},
            operation_name="get_log_events",
        )
        with self.assertRaisesRegex(Exception, "Couldn't find.*"):
            aws_container_logs.get_cloudwatch_logs("foo", "bar")
            aws_container_logs.cloudwatch_client.get_log_events.assert_called()

        aws_container_logs.cloudwatch_client.get_log_events.reset_mock()
        aws_container_logs.cloudwatch_client.get_log_events.side_effect = ClientError(
            error_response={"Error": {"Code": "SomethingElseHappenedException"}},
            operation_name="get_log_events",
        )
        with self.assertRaisesRegex(Exception, "Unexpected error.*"):
            aws_container_logs.get_cloudwatch_logs("foo", "bar")
            aws_container_logs.cloudwatch_client.get_log_events.assert_called()

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_parse_container_arn(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        with self.assertRaisesRegex(Exception, "Container arn is missing.*"):
            aws_container_logs._parse_container_arn(None)

        bad_arn = "abc:123"
        with self.assertRaisesRegex(Exception, "Error in getting service name.*"):
            aws_container_logs._parse_container_arn(bad_arn)

        normal_arn = (
            "arn:aws:ecs:fake-region:123456789:task/fake-container-name/1234abcdef56789"
        )
        expected = ["ecs", "fake-container-name", "1234abcdef56789"]
        self.assertEqual(expected, aws_container_logs._parse_container_arn(normal_arn))

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_parse_log_events(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        events = [
            {"message": "hello", "code": 200, "other": "ignore"},
            {"message": "world", "code": 200, "other": "ignore"},
        ]
        expected = ["hello", "world"]
        self.assertEqual(expected, aws_container_logs._parse_log_events(events))

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_get_container_name_id(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        bad_task_id = "abc/123"
        with self.assertRaisesRegex(Exception, "Error in getting container name.*"):
            aws_container_logs._get_container_name_id(bad_task_id)

        # Simple test
        normal_task_id = "task/container-name/abc123"
        expected = ["container-name", "abc123"]
        self.assertEqual(
            expected, aws_container_logs._get_container_name_id(normal_task_id)
        )

        # Replace -cluster
        cluster_task_id = "task/my-cluster/abc123"
        expected = ["my-container", "abc123"]
        self.assertEqual(
            expected, aws_container_logs._get_container_name_id(cluster_task_id)
        )

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_verify_log_group(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        aws_container_logs.cloudwatch_client.describe_log_groups.return_value = {
            "logGroups": ["my_log_group"]
        }
        self.assertTrue(aws_container_logs._verify_log_group("my_log_group"))

        aws_container_logs.cloudwatch_client.describe_log_groups.reset_mock()
        aws_container_logs.cloudwatch_client.describe_log_groups.side_effect = (
            ClientError(
                error_response={"Error": {"Code": "InvalidParameterException"}},
                operation_name="describe_log_groups",
            )
        )
        with self.assertRaisesRegex(Exception, "Wrong parameters.*"):
            aws_container_logs._verify_log_group("my_log_group")

        aws_container_logs.cloudwatch_client.describe_log_groups.reset_mock()
        aws_container_logs.cloudwatch_client.describe_log_groups.side_effect = (
            ClientError(
                error_response={"Error": {"Code": "ResourceNotFoundException"}},
                operation_name="describe_log_groups",
            )
        )
        with self.assertRaisesRegex(Exception, "Couldn't find.*"):
            aws_container_logs._verify_log_group("my_log_group")

        aws_container_logs.cloudwatch_client.describe_log_groups.reset_mock()
        aws_container_logs.cloudwatch_client.describe_log_groups.side_effect = (
            ClientError(
                error_response={"Error": {"Code": "SomethingElseHappenedException"}},
                operation_name="describe_log_groups",
            )
        )
        with self.assertRaisesRegex(Exception, "Unexpected error.*"):
            aws_container_logs._verify_log_group("my_log_group")

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_verify_log_stream(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        aws_container_logs.cloudwatch_client.describe_log_streams.return_value = {
            "logStreams": ["my_log_stream"]
        }
        self.assertTrue(
            aws_container_logs._verify_log_stream("my_log_group", "my_log_stream")
        )

        aws_container_logs.cloudwatch_client.describe_log_streams.reset_mock()
        aws_container_logs.cloudwatch_client.describe_log_streams.side_effect = (
            ClientError(
                error_response={"Error": {"Code": "InvalidParameterException"}},
                operation_name="describe_log_streams",
            )
        )
        with self.assertRaisesRegex(Exception, "Wrong parameters.*"):
            aws_container_logs._verify_log_stream("my_log_group", "my_log_stream")

        aws_container_logs.cloudwatch_client.describe_log_streams.reset_mock()
        aws_container_logs.cloudwatch_client.describe_log_streams.side_effect = (
            ClientError(
                error_response={"Error": {"Code": "ResourceNotFoundException"}},
                operation_name="describe_log_streams",
            )
        )
        with self.assertRaisesRegex(Exception, "Couldn't find.*"):
            aws_container_logs._verify_log_stream("my_log_group", "my_log_stream")

        aws_container_logs.cloudwatch_client.describe_log_streams.reset_mock()
        aws_container_logs.cloudwatch_client.describe_log_streams.side_effect = (
            ClientError(
                error_response={"Error": {"Code": "SomethingElseHappenedException"}},
                operation_name="describe_log_streams",
            )
        )
        with self.assertRaisesRegex(Exception, "Unexpected error.*"):
            aws_container_logs._verify_log_stream("my_log_group", "my_log_stream")

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_create_s3_folder(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        aws_container_logs.s3_client.put_object.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 200}
        }
        self.assertIsNone(aws_container_logs.create_s3_folder("bucket", "folder"))
        aws_container_logs.s3_client.put_object.assert_called_once_with(
            Bucket="bucket", Key="folder"
        )

        aws_container_logs.s3_client.put_object.reset_mock()
        aws_container_logs.s3_client.put_object.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 403}
        }
        with self.assertRaisesRegex(Exception, "Failed to create.*"):
            aws_container_logs.create_s3_folder("bucket", "folder")

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_ensure_folder_exists(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        aws_container_logs.s3_client.list_objects_v2.return_value = {
            "Contents": ["a", "b", "c"]
        }
        self.assertTrue(aws_container_logs.ensure_folder_exists("bucket", "folder"))

        aws_container_logs.s3_client.list_objects_v2.reset_mock()
        aws_container_logs.s3_client.list_objects_v2.return_value = {}
        self.assertFalse(aws_container_logs.ensure_folder_exists("bucket", "folder"))

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_get_s3_folder_contents(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        expected = {"ContinuationToken": "abc123", "Contents": ["a", "b", "c"]}
        aws_container_logs.s3_client.list_objects_v2.return_value = expected
        self.assertEqual(
            expected, aws_container_logs.get_s3_folder_contents("bucket", "folder")
        )

        # Check that continuation token is set
        aws_container_logs.s3_client.list_objects_v2.reset_mock()
        aws_container_logs.s3_client.list_objects_v2.return_value = expected
        self.assertEqual(
            expected,
            aws_container_logs.get_s3_folder_contents("bucket", "folder", "def678"),
        )
        aws_container_logs.s3_client.list_objects_v2.assert_called_once_with(
            Bucket="bucket",
            Prefix="folder",
            ContinuationToken="def678",
        )

        # check exception cases
        aws_container_logs.s3_client.list_objects_v2.reset_mock()
        aws_container_logs.s3_client.list_objects_v2.side_effect = ClientError(
            error_response={"Error": {"Code": "InvalidParameterException"}},
            operation_name="list_objects_v2",
        )
        with self.assertRaisesRegex(Exception, "Couldn't find folder.*"):
            aws_container_logs.get_s3_folder_contents("bucket", "folder")

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_get_s3_folder_path(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        aws_container_logs.S3_LOGGING_FOLDER = "aaa"
        expected = "aaa/bbb/ccc"
        self.assertEqual(expected, aws_container_logs._get_s3_folder_path("bbb", "ccc"))

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_get_files_to_download_logs(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        expected = ["a", "b", "c"]
        # Basic test
        aws_container_logs.s3_client.list_objects_v2.side_effect = [
            {
                "Contents": [{"Key": "a"}, {"Key": "b"}, {"Key": "c"}],
            }
        ]
        self.assertEqual(
            expected, aws_container_logs._get_files_to_download_logs("bucket", "folder")
        )

        # Check with continuation tokens
        aws_container_logs.s3_client.list_objects_v2.reset_mock()
        aws_container_logs.s3_client.list_objects_v2.side_effect = [
            {"NextContinuationToken": "abc123", "Contents": [{"Key": "a"}]},
            {"NextContinuationToken": "abc456", "Contents": [{"Key": "b"}]},
            {"Contents": [{"Key": "c"}]},
        ]
        self.assertEqual(
            expected, aws_container_logs._get_files_to_download_logs("bucket", "folder")
        )

        # Ensure folders aren't included
        aws_container_logs.s3_client.list_objects_v2.side_effect = [
            {
                "Contents": [
                    {"Key": "f/"},
                    {"Key": "a"},
                    {"Key": "f2/"},
                    {"Key": "b"},
                    {"Key": "c"},
                ],
            }
        ]
        self.assertEqual(
            expected, aws_container_logs._get_files_to_download_logs("bucket", "folder")
        )

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    @patch("fbpcs.infra.logging_service.download_logs.download_logs.Utils")
    def test_download_logs(self, mock_utils, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        aws_container_logs.s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "f/"},
                {"Key": "a"},
                {"Key": "f2/"},
                {"Key": "b"},
                {"Key": "c"},
            ],
        }
        expected_files_to_download = ["a", "b", "c"]

        # no local_download_dir
        expected_local_path = f"{aws_container_logs.DEFAULT_DOWNLOAD_LOCATION}/tag"
        aws_container_logs.download_logs("bucket", "tag")
        aws_container_logs.utils.create_folder.assert_called_once()
        for f in expected_files_to_download:
            aws_container_logs.s3_client.download_file.assert_any_call(
                Bucket="bucket", Key=f, Filename=f"{expected_local_path}/{f}"
            )

        # override local_download_dir
        aws_container_logs.s3_client.download_file.reset_mock()
        aws_container_logs.utils.create_folder.reset_mock()
        expected_local_path = "/tmp/tag"
        aws_container_logs.download_logs("bucket", "tag", "/tmp")
        aws_container_logs.utils.create_folder.assert_called_once()
        for f in expected_files_to_download:
            aws_container_logs.s3_client.download_file.assert_any_call(
                Bucket="bucket", Key=f, Filename=f"{expected_local_path}/{f}"
            )

        # Make folder not exist
        aws_container_logs.s3_client.download_file.reset_mock()
        aws_container_logs.utils.create_folder.reset_mock()
        aws_container_logs.s3_client.list_objects_v2.reset_mock()
        aws_container_logs.s3_client.list_objects_v2.return_value = {}
        with self.assertRaisesRegex(Exception, "Folder .* not found.*"):
            aws_container_logs.download_logs("bucket", "tag")

    @patch("fbpcs.infra.logging_service.download_logs.cloud.aws_cloud.boto3")
    def test_upload_logs_to_s3_from_cloudwatch(self, mock_boto3) -> None:
        aws_container_logs = AwsContainerLogs("my_tag")
        aws_container_logs.cloudwatch_client.get_log_events.side_effect = [
            {"events": [{"message": "123"}], "nextForwardToken": "1"},
            {"events": [{"message": "456"}], "nextForwardToken": "2"},
            {"events": [{"message": "789"}], "nextForwardToken": "3"},
            # Repeated event indicates no more data available
            {"events": [{"message": "789"}], "nextForwardToken": "3"},
        ]

        aws_container_logs.cloudwatch_client.describe_log_groups.return_value = {
            "logGroups": ["my_log_group"]
        }

        aws_container_logs.cloudwatch_client.describe_log_streams.return_value = {
            "logStreams": ["my_log_stream"]
        }

        aws_container_logs.s3_client.put_object.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 200}
        }

        arn = (
            "arn:aws:ecs:fake-region:123456789:task/fake-container-name/1234abcdef56789"
        )
        expected_key = f"{aws_container_logs.S3_LOGGING_FOLDER}/my_tag/1234abcdef56789"
        expected_body = "123\n456\n789".encode("utf-8")

        # folders already exist, no need to create
        aws_container_logs.s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "f/"},
                {"Key": "a"},
                {"Key": "f2/"},
                {"Key": "b"},
                {"Key": "c"},
            ],
        }
        aws_container_logs.upload_logs_to_s3_from_cloudwatch("bucket", arn)
        aws_container_logs.s3_client.put_object.assert_called_once_with(
            Body=expected_body, Bucket="bucket", Key=expected_key
        )

        # folders don't exist, create first
        # TODO: Put this repeated code in a setUp block
        aws_container_logs.cloudwatch_client.get_log_events.reset_mock()
        aws_container_logs.cloudwatch_client.get_log_events.side_effect = [
            {"events": [{"message": "123"}], "nextForwardToken": "1"},
            {"events": [{"message": "456"}], "nextForwardToken": "2"},
            {"events": [{"message": "789"}], "nextForwardToken": "3"},
            # Repeated event indicates no more data available
            {"events": [{"message": "789"}], "nextForwardToken": "3"},
        ]
        aws_container_logs.s3_client.list_objects_v2.reset_mock()
        aws_container_logs.s3_client.list_objects_v2.return_value = {}
        aws_container_logs.upload_logs_to_s3_from_cloudwatch("bucket", arn)
        aws_container_logs.s3_client.put_object.assert_any_call(
            Bucket="bucket",
            Key=f"{aws_container_logs.S3_LOGGING_FOLDER}/",
        )
        aws_container_logs.s3_client.put_object.assert_any_call(
            Bucket="bucket",
            Key=f"{aws_container_logs.S3_LOGGING_FOLDER}/my_tag/",
        )
        aws_container_logs.s3_client.put_object.assert_any_call(
            Body=expected_body, Bucket="bucket", Key=expected_key
        )

        ###############
        # Error cases #
        ###############
        # NoSuchBucket from head_bucket
        aws_container_logs.s3_client.head_bucket.reset_mock()
        aws_container_logs.s3_client.head_bucket.side_effect = ClientError(
            error_response={"Error": {"Code": "NoSuchBucket"}},
            operation_name="head_bucket",
        )
        with self.assertRaisesRegex(Exception, "Couldn't find bucket.*"):
            aws_container_logs.upload_logs_to_s3_from_cloudwatch("bucket", arn)
            aws_container_logs.s3_client.head_bucket.assert_called()

        # Generic exception from head_bucket
        aws_container_logs.s3_client.head_bucket.reset_mock()
        aws_container_logs.s3_client.head_bucket.side_effect = ClientError(
            error_response={"Error": {"Code": "SomethingElseHappenedException"}},
            operation_name="head_bucket",
        )
        with self.assertRaisesRegex(Exception, "Couldn't find the S3.*"):
            aws_container_logs.upload_logs_to_s3_from_cloudwatch("bucket", arn)
            aws_container_logs.s3_client.head_bucket.assert_called()

        # Can't verify log group
        aws_container_logs.s3_client.head_bucket.reset_mock(side_effect=True)
        aws_container_logs.cloudwatch_client.describe_log_groups.side_effect = (
            ClientError(
                error_response={"Error": {"Code": "InvalidParameterException"}},
                operation_name="describe_log_groups",
            )
        )
        with self.assertRaisesRegex(Exception, "Couldn't find log group.*"):
            aws_container_logs.upload_logs_to_s3_from_cloudwatch("bucket", arn)

        # Can't verify log stream
        aws_container_logs.cloudwatch_client.describe_log_groups.reset_mock(
            side_effect=True
        )
        aws_container_logs.cloudwatch_client.describe_log_groups.return_value = {
            "logGroups": ["my_log_group"]
        }
        aws_container_logs.cloudwatch_client.describe_log_streams.side_effect = (
            ClientError(
                error_response={"Error": {"Code": "InvalidParameterException"}},
                operation_name="describe_log_streams",
            )
        )
        with self.assertRaisesRegex(Exception, "Couldn't find log stream.*"):
            aws_container_logs.upload_logs_to_s3_from_cloudwatch("bucket", arn)