from openg2p_llm_common.errors import BaseLlmCommonException


class AuthMissingUserId(BaseLlmCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-UCA-103",
            "Missing user_id key auth credentials. Set valid value for `config.user_id_key_in_auth`.",
            **kwargs,
        )
