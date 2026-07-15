from datetime import date, datetime

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y년 %m월 %d일",
)
DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y.%m.%d %H:%M:%S",
    "%Y년 %m월 %d일 %H시 %M분 %S초",
)
DATE_OUTPUT_FORMAT = "%Y년 %m월 %d일"
DATETIME_OUTPUT_FORMAT = "%Y년 %m월 %d일 %H시 %M분 %S초"


def _normalize(
    value: str | date | datetime,
    input_formats: tuple[str, ...],
    output_format: str,
) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime(output_format)

    for fmt in input_formats:
        try:
            return datetime.strptime(value, fmt).strftime(output_format)
        except ValueError:
            continue

    raise ValueError(f"Unsupported format. Expected {', '.join(input_formats)}.")


def normalize_date(value: str | date) -> str:
    return _normalize(value, DATE_FORMATS, DATE_OUTPUT_FORMAT)


def normalize_datetime(value: str | datetime) -> str:
    return _normalize(value, DATETIME_FORMATS, DATETIME_OUTPUT_FORMAT)
