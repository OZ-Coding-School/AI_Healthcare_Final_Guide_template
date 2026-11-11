"""
추론 단계의 예외입니다. Worker와 API가 사용자 오류와 서버 오류를 구분해 응답할 수 있도록 나눕니다.

- InferenceInputError: 사용자 입력이 잘못된 경우 (API 400 대응)
- ModelArtifactError: 모델 번들이 없거나 손상·불일치한 경우 (API 500 대응)

메시지에는 입력값을 넣지 않습니다. 건강 정보가 로그나 응답으로 새지 않도록 필드명과 사유만 담습니다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class InputFieldError:
    field: str
    reason: str


class InferenceInputError(ValueError):
    def __init__(self, errors: list[InputFieldError]) -> None:
        if not errors:
            raise ValueError("errors must not be empty")
        self.errors = errors
        summary = ", ".join(f"{error.field}: {error.reason}" for error in errors)
        super().__init__(f"Invalid inference input ({summary})")


class ModelArtifactError(RuntimeError):
    pass
