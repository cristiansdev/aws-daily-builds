package com.portfolio.reconciliation;

public class TransaccionInvalidaException extends RuntimeException{
    public TransaccionInvalidaException(String mensaje) {
        super(mensaje);
    }  
}
