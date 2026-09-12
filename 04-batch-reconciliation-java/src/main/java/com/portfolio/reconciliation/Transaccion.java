package com.portfolio.reconciliation;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

public class Transaccion extends RuntimeException{
    @JsonProperty ("id_transaccion")
    public String idTransaccion;

    @JsonProperty("cuenta")
    public String cuenta;

    @JsonProperty("monto")
    public Double monto;

    @JsonProperty("tipo")
    public String tipo;

    private static final List<String> TIPOS_VALIDOS = List.of("deposito", "retiro", "transferencia");

    public void validar() {
        if (idTransaccion == null || idTransaccion.isBlank()) {
            throw new TransaccionInvalidaException("id_transaccion es requerido");
        }
        if (cuenta == null || cuenta.isBlank()) {
            throw new TransaccionInvalidaException("cuenta es requerida");
        }
        if (monto == null || monto <= 0) {
            throw new TransaccionInvalidaException("monto debe ser mayor a 0");
        }
        if (tipo == null || !TIPOS_VALIDOS.contains(tipo)) {
            throw new TransaccionInvalidaException("tipo debe ser uno de: " + TIPOS_VALIDOS);
        }
    }

    
}
