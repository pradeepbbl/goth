# coding: utf-8

"""
    Yagna Activity API

    It conforms with capability level 1 of the [Activity API specification](https://docs.google.com/document/d/1BXaN32ediXdBHljEApmznSfbuudTU8TmvOmHKl0gmQM).  # noqa: E501

    The version of the OpenAPI document: v1
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six

from openapi_activity_client.configuration import Configuration


class ActivityUsage(object):
    """NOTE: This class is auto generated by OpenAPI Generator.
    Ref: https://openapi-generator.tech

    Do not edit the class manually.
    """

    """
    Attributes:
      openapi_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    openapi_types = {
        'current_usage': 'list[float]',
        'timestamp': 'int'
    }

    attribute_map = {
        'current_usage': 'currentUsage',
        'timestamp': 'timestamp'
    }

    def __init__(self, current_usage=None, timestamp=None, local_vars_configuration=None):  # noqa: E501
        """ActivityUsage - a model defined in OpenAPI"""  # noqa: E501
        if local_vars_configuration is None:
            local_vars_configuration = Configuration()
        self.local_vars_configuration = local_vars_configuration

        self._current_usage = None
        self._timestamp = None
        self.discriminator = None

        if current_usage is not None:
            self.current_usage = current_usage
        if timestamp is not None:
            self.timestamp = timestamp

    @property
    def current_usage(self):
        """Gets the current_usage of this ActivityUsage.  # noqa: E501

        Current usage vector  # noqa: E501

        :return: The current_usage of this ActivityUsage.  # noqa: E501
        :rtype: list[float]
        """
        return self._current_usage

    @current_usage.setter
    def current_usage(self, current_usage):
        """Sets the current_usage of this ActivityUsage.

        Current usage vector  # noqa: E501

        :param current_usage: The current_usage of this ActivityUsage.  # noqa: E501
        :type: list[float]
        """

        self._current_usage = current_usage

    @property
    def timestamp(self):
        """Gets the timestamp of this ActivityUsage.  # noqa: E501

        Usage update timestamp (UTC)  # noqa: E501

        :return: The timestamp of this ActivityUsage.  # noqa: E501
        :rtype: int
        """
        return self._timestamp

    @timestamp.setter
    def timestamp(self, timestamp):
        """Sets the timestamp of this ActivityUsage.

        Usage update timestamp (UTC)  # noqa: E501

        :param timestamp: The timestamp of this ActivityUsage.  # noqa: E501
        :type: int
        """

        self._timestamp = timestamp

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.openapi_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, ActivityUsage):
            return False

        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        if not isinstance(other, ActivityUsage):
            return True

        return self.to_dict() != other.to_dict()
