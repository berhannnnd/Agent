# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：register_exception.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import traceback
from typing import Union

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from pydantic_core import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from gateway.core.exceptions import AuthenticationException, ServerException
from gateway.core.logging import logger
from gateway.shared.server.common.base_resp import NotFound, ServerError, UnProcessable, Unauthorized, fail


async def log_error(
    request: Request,
    exc: Union[ServerException, ValidationError, StarletteHTTPException, Exception],
):
    """记录异常并返回统一响应。"""
    if isinstance(exc, RequestValidationError):
        error_msg = exc.errors()
        response = UnProcessable.model_copy(deep=True)
    elif isinstance(exc, ResponseValidationError):
        error_msg = exc.errors()
        response = ServerError.model_copy(deep=True)
    elif isinstance(exc, AuthenticationException):
        error_msg = exc.errors
        response = Unauthorized.model_copy(deep=True)
    elif isinstance(exc, ServerException):
        error_msg = exc.errors
        response = ServerError.model_copy(deep=True)
    elif isinstance(exc, ValidationError):
        error_msg = exc.errors()
        response = ServerError.model_copy(deep=True)
    elif isinstance(exc, StarletteHTTPException):
        error_msg = exc.detail
        response = NotFound.model_copy(deep=True)
    else:
        error_msg = f"[内部异常错误]{exc}"
        response = ServerError.model_copy(deep=True)

    request_id = getattr(request.state, "request_id", "unknown")
    response.detail = error_msg
    response.request_id = request_id

    logger.error(
        "Exception  : %s\n"
        "====================ERROR======================\n"
        "RequestId  : %s\n"
        "Host       : %s\n"
        "URL        : %s %s\n"
        "UserAgent  : %s\n\n"
        "%s\n"
        "===============================================",
        error_msg,
        request_id,
        request.client.host if request.client else "unknown",
        request.method,
        request.url,
        request.headers.get("user-agent"),
        traceback.format_exc(),
    )

    return fail(response)


def register_exception(app: FastAPI) -> None:
    """注册全局异常捕获。"""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return await log_error(request, exc)

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
        return await log_error(request, exc)

    @app.exception_handler(ResponseValidationError)
    async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
        return await log_error(request, exc)

    @app.exception_handler(AuthenticationException)
    async def authentication_exception_handler(request: Request, exc: AuthenticationException):
        return await log_error(request, exc)

    @app.exception_handler(ServerException)
    async def server_exception_handler(request: Request, exc: ServerException):
        return await log_error(request, exc)

    @app.exception_handler(Exception)
    async def all_exception_handler(request: Request, exc: Exception):
        return await log_error(request, exc)
