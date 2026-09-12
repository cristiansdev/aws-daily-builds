package com.portfolio.reconciliation;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.SQSEvent;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;

public class ReconciliationHandler implements RequestHandler<SQSEvent, Void>{

    private static final DynamoDbClient dynamoDb = DynamoDbClient.create();
    private static final String TABLE_NAME = System.getenv("TABLE_NAME");

    @Override
    public Void handleRequest(SQSEvent event, Context context) {
        
        List<SQSEvent.SQSMessage> mensajes = event.getRecords();
        
        for(SQSEvent.SQSMessage mensaje: mensajes){
             String cuerpo = mensaje.getBody();
                String mensajeId = mensaje.getMessageId();
                ObjectMapper mapper = new ObjectMapper();
            try {
                Transaccion transaccion = mapper.readValue(cuerpo, Transaccion.class);
                transaccion.validar();
                guardarEnDynamo(transaccion, context);
                context.getLogger().log("Procesando mensaje" + mensajeId);
            } catch (JsonProcessingException e) {
                context.getLogger().log("Error procesando mensaje " + mensajeId + ": " + e.getMessage());
                throw new RuntimeException("Fallo al procesar mensaje " + mensajeId, e);
            } catch(TransaccionInvalidaException e){
                context.getLogger().log("Transacción inválida en mensaje " + mensajeId + ": " + e.getMessage());
                throw e;
            }
        }
        return null;
    }

    private void guardarEnDynamo(Transaccion t, Context context){
        Map<String, AttributeValue> item = new HashMap<>();
        item.put("id_transaccion", AttributeValue.builder().s(t.idTransaccion).build());
        item.put("cuenta", AttributeValue.builder().s(t.cuenta).build());
        item.put("monto", AttributeValue.builder().n(t.monto.toString()).build());
        item.put("tipo", AttributeValue.builder().s(t.tipo).build());

        PutItemRequest request = PutItemRequest.builder()
                .tableName(TABLE_NAME)
                .item(item)
                .conditionExpression("attribute_not_exists(id_transaccion)")
                .build();

        try {
            dynamoDb.putItem(request);
        } catch (ConditionalCheckFailedException e) {
            context.getLogger().log("Duplicado ignorado: " + t.idTransaccion);
        }
    }
    
}
