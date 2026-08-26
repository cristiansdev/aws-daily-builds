import { describe, it, expect, beforeEach } from "vitest";
import { mockClient } from "aws-sdk-client-mock";
import {
  DynamoDBDocumentClient,
  GetCommand,
  PutCommand,
  DeleteCommand,
  ScanCommand,
} from "@aws-sdk/lib-dynamodb";
import { handler } from "../src/index";
import type { APIGatewayProxyEventV2 } from "aws-lambda";

process.env.TABLE_NAME = "test-table";

const ddbMock = mockClient(DynamoDBDocumentClient);

beforeEach(() => {
  ddbMock.reset();
});

function fakeEvent(
  method: string,
  id?: string,
  body?: unknown,
): APIGatewayProxyEventV2 {
  return {
    requestContext: { http: { method } },
    pathParameters: id ? { id } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  } as APIGatewayProxyEventV2;
}

describe("tasks handler", () => {
  it("GET /tasks/{id} — regresa la tarea si existe", async () => {
    ddbMock.on(GetCommand).resolves({ Item: { id: "1", title: "comprar leche" } });

    const res = await handler(fakeEvent("GET", "1"));

    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body!)).toEqual({ id: "1", title: "comprar leche" });
  });

  it("GET /tasks/{id} — 404 si no existe", async () => {
    ddbMock.on(GetCommand).resolves({ Item: undefined });

    const res = await handler(fakeEvent("GET", "999"));

    expect(res.statusCode).toBe(404);
  });

  it("GET /tasks — lista todas las tareas", async () => {
    ddbMock.on(ScanCommand).resolves({ Items: [{ id: "1", title: "a" }, { id: "2", title: "b" }] });

    const res = await handler(fakeEvent("GET"));

    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body!)).toHaveLength(2);
  });

  it("POST /tasks — crea una tarea nueva", async () => {
    ddbMock.on(PutCommand).resolves({});

    const res = await handler(fakeEvent("POST", undefined, { title: "nueva tarea" }));

    expect(res.statusCode).toBe(201);
    const created = JSON.parse(res.body!);
    expect(created.title).toBe("nueva tarea");
    expect(created.id).toBeDefined();
  });

  it("POST /tasks — 400 si falta el body", async () => {
    const res = await handler(fakeEvent("POST"));

    expect(res.statusCode).toBe(400);
  });

  it("DELETE /tasks/{id} — 204 al borrar", async () => {
    ddbMock.on(DeleteCommand).resolves({});

    const res = await handler(fakeEvent("DELETE", "1"));

    expect(res.statusCode).toBe(204);
  });
});