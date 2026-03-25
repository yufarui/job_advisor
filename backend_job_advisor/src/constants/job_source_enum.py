from enum import Enum


class JobSourceEnum(str, Enum):
    """职位来源"""

    internal = "internal"
    crawler = "crawler"
    partner_api = "partner_api"
    user_import = "user_import"
    unknown = "unknown"
