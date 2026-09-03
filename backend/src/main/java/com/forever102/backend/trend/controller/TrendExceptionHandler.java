package com.forever102.backend.trend.controller;

import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.global.response.ErrorResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

@RestControllerAdvice(assignableTypes = TrendController.class)
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TrendExceptionHandler {

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ErrorResponse> handleInvalidId(MethodArgumentTypeMismatchException exception) {
        return ResponseEntity.badRequest().body(ErrorResponse.of(ErrorCode.VALIDATION_ERROR.getMessage()));
    }

    @ExceptionHandler(HandlerMethodValidationException.class)
    public ResponseEntity<ErrorResponse> handleValidation(HandlerMethodValidationException exception) {
        return ResponseEntity.status(exception.getStatusCode())
                .body(ErrorResponse.of(exception.isForReturnValue()
                        ? ErrorCode.INTERNAL_SERVER_ERROR.getMessage() : ErrorCode.VALIDATION_ERROR.getMessage()));
    }
}
