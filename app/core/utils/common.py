import re


def normalize_phone_number(phone_number: str) -> str:
    if phone_number.startswith("+82"):
        phone_number = "0" + phone_number[3:]
    phone_number = re.sub(r"\D", "", phone_number)

    return phone_number


def get_enum_max_length(enum):
    return max(len(member.name) for member in enum)
