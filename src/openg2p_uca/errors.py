from openg2p_fastapi_common.errors import BaseAppException


class UcaCommonException(BaseAppException):
    """
    Common UCA Exception
    """


class GetMessagesMissingParamsError(UcaCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-UCA-102",
            "Missing Parameters. Neither thread_id nor message_id nor user_id are specified.",
            **kwargs,
        )


class AuthMissingUserId(UcaCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-UCA-103",
            "Missing user_id key auth credentials. Set valid value for `config.user_id_key_in_auth`.",
            **kwargs,
        )


class ToolNotFound(UcaCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-UCA-104",
            "Tool with the given name not found.",
            **kwargs,
        )


class ToolInvalidRequestResponse(UcaCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-UCA-105",
            "Invalid request or response type defined in the Tool.",
            **kwargs,
        )


class ThreadIdInvalid(UcaCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-UCA-404",
            "Thread id not found or invalid.",
            http_status_code=400,
            **kwargs,
        )
