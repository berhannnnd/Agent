# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：base_resp.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from typing import Any, Optional, Union

from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.core.logging import logger


class Resp(BaseModel):
    code: Union[int, str] = "0000"
    message: str = "success"
    success: bool = True
    http_status: int = http_status.HTTP_200_OK
    detail: Union[str, list, dict] = ""
    request_id: Union[str, int] = ""
    data: Optional[Any] = None

    @property
    def resp_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "success": self.success,
            "data": self.data,
        }

    @property
    def info_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "code": self.code,
            "message": self.message,
            "success": self.success,
            "data": self.data,
        }


def ok(response: Resp, data: Optional[Any] = None) -> Response:
    logger.info("\n\n=====================DONE========================\n%s\n", response.info_dict)
    return JSONResponse(
        status_code=http_status.HTTP_200_OK,
        content=jsonable_encoder(data if data is not None else response.resp_dict),
    )


def fail(response: Resp) -> Response:
    response.data = {"request_id": response.request_id, "detail": response.detail}
    response.message = "failed"
    response.success = False
    if response.code == "0000":
        response.code = "9999"

    logger.error("\n\n=====================DONE========================\n%s\n", response.info_dict)
    return JSONResponse(
        status_code=response.http_status,
        content=jsonable_encoder(response.resp_dict),
    )


Unauthorized = Resp(
    code="401",
    message="权限拒绝",
    success=False,
    http_status=http_status.HTTP_401_UNAUTHORIZED,
)
Forbidden = Resp(
    code="403",
    message="权限不足",
    success=False,
    http_status=http_status.HTTP_403_FORBIDDEN,
)
NotFound = Resp(
    code="404",
    message="资源不存在",
    success=False,
    http_status=http_status.HTTP_404_NOT_FOUND,
)
UnProcessable = Resp(
    code="422",
    message="请求参数错误",
    success=False,
    http_status=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
)
ServerError = Resp(
    code="500",
    message="系统调用异常",
    success=False,
    http_status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
)
