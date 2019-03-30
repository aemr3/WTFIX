# This file is a part of WTFIX.
#
# Copyright (C) 2018,2019 John Cass <john.cass77@gmail.com>
#
# WTFIX is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# WTFIX is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
# License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import abc

from wtfix.conf import settings
from wtfix.core import utils
from wtfix.core.exceptions import (
    ValidationError,
    TagNotFound,
    UnknownType,
    DuplicateTags,
)
from wtfix.protocol.common import Tag, MsgType
from .fieldset import OrderedDictFieldSet, ListFieldSet


class FIXMessage(abc.ABC):
    """
    Mixin class that promotes FieldSets to FIX messages. Provides often-used shortcuts for common tag number
    lookups.
    """

    def __format__(self, format_spec):
        """
        :return: name (type): ((tag_name_1, value_1), (tag_name_2, value_2))
        """
        return f"{self.name} ({self.type}): {super().__format__(format_spec)}"

    def __str__(self):
        """
        :return: type: ((tag_1, value_1), (tag_2, value_2))
        """
        return f"{self.type}: {super().__str__()}"

    @property
    def type(self):
        """
        The type of this Message, as denoted by tag 35.
        :return: Value of tag 35 or None if no message type has been defined.
        """
        try:
            return str(self[Tag.MsgType])
        except TagNotFound:
            return None

    @property
    def name(self):
        """
        :return: Human friendly name of this type of Message, based on tag 35, or 'Unknown' if name
        could not be determined.
        """
        try:
            return MsgType.get_name(self.type)
        except UnknownType:
            return "Unknown"

    @property
    def seq_num(self):
        """
        :return: Message sequence number
        """
        try:
            return int(self[Tag.MsgSeqNum])
        except TagNotFound:
            return None

    @seq_num.setter
    def seq_num(self, value):
        self[Tag.MsgSeqNum] = value

    @property
    def sender_id(self):
        try:
            return str(self[Tag.SenderCompID])
        except TagNotFound:
            return None

    @sender_id.setter
    def sender_id(self, value):
        self[Tag.SenderCompID] = value

    @property
    def target_id(self):
        try:
            return str(self[Tag.TargetCompID])
        except TagNotFound:
            return None

    @target_id.setter
    def target_id(self, value):
        self[Tag.TargetCompID] = value

    @abc.abstractmethod
    def copy(self):
        """
        Make a copy of this message
        """

    def validate(self):
        """
        A well-formed message should, at minimum, contain tag 35.

        :return: A valid Message.
        :raises: ValidationError if the message is not valid.
        """
        try:
            self[Tag.MsgType]
        except TagNotFound as e:
            raise ValidationError(f"No 'MsgType (35)' specified for {self}.") from e

        return self


class RawMessage(FIXMessage, OrderedDictFieldSet):
    """
    A raw message with most of its content still in byte-encoded format.

    Useful for situations where only the standard header fields and checksum is required, and the
    overhead that will be incurred in parsing the remaining tags is unnecessary.
    """

    def __init__(
        self,
        begin_string=None,
        body_length=None,
        message_type=None,
        message_seq_num=None,
        encoded_body=None,
        checksum=None,
    ):

        if begin_string is None:
            begin_string = settings.BEGIN_STRING

        if encoded_body is None:
            encoded_body = b""

        self.encoded_body = encoded_body

        if body_length is None:
            body_length = len(encoded_body)

        if checksum is None:
            checksum = utils.calculate_checksum(encoded_body)

        super().__init__(
            (Tag.BeginString, begin_string),
            (Tag.BodyLength, body_length),
            (Tag.MsgType, message_type),
            (Tag.MsgSeqNum, message_seq_num),
            (Tag.CheckSum, checksum),
        )

    def copy(self):
        return RawMessage(
            begin_string=self.BeginString.value,
            body_length=self.BodyLength.value,
            message_type=self.MsgType.value,
            message_seq_num=self.MsgSeqNum.value,
            encoded_body=self.encoded_body,
            checksum=self.CheckSum.value,
        )

    def __format__(self, format_spec):
        """
        :return: name (type): ((tag_name_1, value_1), (tag_name_2, value_2))
        """
        return f"{super().__format__(format_spec)}, with byte-encoded content: {self.encoded_body}"

    def __str__(self):
        """
        :return: name (type): ((tag_name_1, value_1), (tag_name_2, value_2))
        """
        return f"{super().__str__()}, with byte-encoded content: {self.encoded_body}"


def generic_message_factory(*fields, **kwargs):
    try:
        return OptimizedGenericMessage(
            *fields, **kwargs
        )  # Try to instantiate a OptimizedGenericMessage first
    except DuplicateTags:
        return GenericMessage(*fields, **kwargs)  # Fall back to GenericMessage


class GenericMessage(FIXMessage, ListFieldSet):
    """
    The most basic type of FIX Message, consisting of one or more Fields in a FieldSet.

    We think of FIX messages as lists of (tag, value) pairs, where tag is a number and value is a bytestring.
    """

    def copy(self):
        copy = GenericMessage()
        copy._data = self._data.copy()

        return copy


class OptimizedGenericMessage(FIXMessage, OrderedDictFieldSet):
    """
    An optimized implementation based on storing fields in a dictionary instead of a list.
    """

    def __eq__(self, other):
        if super().__eq__(other):
            return self.group_templates == other.group_templates

    def copy(self):
        copy = OptimizedGenericMessage()
        copy.group_templates = self.group_templates.copy()

        copy._data = self._data.copy()

        return copy
