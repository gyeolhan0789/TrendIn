package com.forever102.backend.global.exception;

import java.util.Optional;

import com.forever102.backend.global.response.ErrorResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.support.DefaultMessageSourceResolvable;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;


@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> handleBusinessException(BusinessException e) {
        log.error("사용자 정의 에러 발생 : message : {}" , e.getErrorCode().getMessage());

        return ResponseEntity
                .status(e.getErrorCode().getStatus())
                .body(
                        ErrorResponse.of(e.getMessage())
                );
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidationException(MethodArgumentNotValidException e) {
        String message = Optional.ofNullable(e.getBindingResult().getFieldError())
                .map(DefaultMessageSourceResolvable::getDefaultMessage)
                .orElse(ErrorCode.VALIDATION_ERROR.getMessage());
        log.error("요청 파라미터 유효성 오류 발생 : {}" , message);
        return ResponseEntity
                .status(ErrorCode.VALIDATION_ERROR.getStatus())
                .body(ErrorResponse.of(message));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ErrorResponse> handleNotReadableException(HttpMessageNotReadableException e) {
        log.error("요청 본문을 읽을 수 없음 : {}" , e.getMessage());
        return ResponseEntity
                .status(ErrorCode.VALIDATION_ERROR.getStatus())
                .body(ErrorResponse.of(ErrorCode.VALIDATION_ERROR.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleException(Exception e) {
        log.error("서버 에러 발생", e);
        return ResponseEntity
                .status(ErrorCode.INTERNAL_SERVER_ERROR.getStatus())
                .body(ErrorResponse.of(ErrorCode.INTERNAL_SERVER_ERROR.getMessage()));
    }
}
