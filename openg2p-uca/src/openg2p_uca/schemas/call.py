from pydantic import BaseModel


class UcaCallOfferRequest(BaseModel):
    sdp: str
    sdp_type: str


class UcaCallOfferResponse(BaseModel):
    type: str
    sdp: str


class UcaCallMetaResponse(BaseModel):
    iceServers: list[dict[str, str]]
