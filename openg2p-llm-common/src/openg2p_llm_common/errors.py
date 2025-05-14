from openg2p_fastapi_common.errors import BaseAppException


class BaseLlmCommonException(BaseAppException):
    """
    Common LLM Exception Base
    """


class GetMessagesMissingParamsError(BaseLlmCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-LLM-102",
            "Missing Parameters. Neither thread_id nor message_id nor user_id are specified.",
            **kwargs,
        )


class ToolNotFound(BaseLlmCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-LLM-104",
            "Tool with the given name not found.",
            **kwargs,
        )


class ToolInvalidRequestResponse(BaseLlmCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-LLM-105",
            "Invalid request or response type defined in the Tool.",
            **kwargs,
        )


class ThreadIdInvalid(BaseLlmCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-LLM-404",
            "Thread id not found or invalid.",
            http_status_code=400,
            **kwargs,
        )
