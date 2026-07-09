from collections.abc import Sequence
from typing import Any


class ConditionalFieldValidationMixin:
    def _normalize_conditional_fields(
        self, field_names: Sequence[str], condition_field: str, expected_value: Any, invert_condition: bool = False
    ) -> None:
        """
        주어진 조건에 따라 관련 필드 값을 정규화하는 메서드입니다.
        조건이 만족되면 필수 필드 값이 유효한지 검사하고, 그렇지 않으면 관련 필드 값을 None으로 설정합니다.

        :param field_names: 관련 필드 이름들의 목록
        :param condition_field: 조건을 확인할 필드 이름
        :param expected_value: 조건에 사용할 예상 값
        :param invert_condition: 조건 결과를 반대로 뒤집을지 여부
        :return: 반환값 없음
        """
        condition = (
            getattr(self, condition_field) != expected_value
            if invert_condition
            else getattr(self, condition_field) == expected_value
        )
        if condition:
            self._validate_required_fields(
                required_field_names=field_names,
            )
        else:
            self._set_fields_to_none(field_names)

    def _validate_required_fields(
        self,
        required_field_names: Sequence[str],
    ) -> None:
        """
        해당 메서드는 주어진 필드 목록에서 값이 None인 필드를 검사하여,
        값이 없는 필드가 있으면 이에 대한 예외를 발생시킵니다.

        :param required_field_names: None 값 여부를 확인할 필드 목록
        :return: 함수가 성공적으로 완료되면 아무 것도 반환하지 않습니다.
        :raises ValueError: 필수 필드 값이 None인 필드가 있으면 예외를 발생시킵니다.
        """
        none_fields = [field_name for field_name in required_field_names if getattr(self, field_name) is None]
        if none_fields:
            fields = ", ".join(none_fields)
            verb = "is" if len(none_fields) == 1 else "are"
            raise ValueError(f"{fields} {verb} required.")

    def _set_fields_to_none(self, field_names: Sequence[str]) -> None:
        """
        주어진 필드의 값을 None으로 설정하는 메서드.

        주어진 `field_names` 리스트를 순회하며 각 필드의 값을 None으로
        설정합니다. 이 메서드는 주로 객체의 특정 속성들을 초기화하거나
        재설정할 때 유용합니다.

        :param field_names: 값을 None으로 설정할 필드 이름들의 시퀀스
        :type field_names: Sequence[str]
        :return: 반환값 없음
        :rtype: None
        """
        for field_name in field_names:
            setattr(self, field_name, None)
