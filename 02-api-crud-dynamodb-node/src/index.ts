import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import {
  DeleteCommand,
  DynamoDBDocumentClient,
  GetCommand,
  PutCommand,
  ScanCommand,
} from "@aws-sdk/lib-dynamodb";
import { randomUUID } from "crypto";
import type {
  APIGatewayProxyEventV2,
  APIGatewayProxyResultV2,
} from "aws-lambda";

const client = new DynamoDBClient({});
const ddb = DynamoDBDocumentClient.from(client);
const TABLE_NAME = process.env.TABLE_NAME!;

export const handler = async (
  event: APIGatewayProxyEventV2,
): Promise<APIGatewayProxyResultV2> => {
  const method = event.requestContext.http.method;
  const id = event.pathParameters?.id;

  if (method === "GET" && id) {
    const result = await ddb.send(
      new GetCommand({
        TableName: TABLE_NAME,
        Key: { id: id },
      }),
    );
    if (result.Item) {
      return {
        statusCode: 200,
        body: JSON.stringify(result.Item),
      };
    }
    return {
      statusCode: 404,
      body: JSON.stringify({ message: "Item not found" }),
    };
  }

  if (method === "POST") {
    if (!event.body) {
      return {
        statusCode: 400,
        body: JSON.stringify({ message: "Missing request body" }),
      };
    }

    const body = JSON.parse(event.body);
    const newTask = {
      id: randomUUID(),
      title: body.title,
      done: false,
    };

    await ddb.send(
      new PutCommand({
        TableName: TABLE_NAME,
        Item: newTask,
      }),
    );

    return {
      statusCode: 201,
      body: JSON.stringify(newTask),
    };
  }
  if (method === "DELETE" && id) {
    await ddb.send(
      new DeleteCommand({
        TableName: TABLE_NAME,
        Key: { id: id },
      }),
    );

    return {
      statusCode: 204,
      body: "",
    };
  }
  if (method === "GET" && !id) {
    const result = await ddb.send(
      new ScanCommand({
        TableName: TABLE_NAME,
      }),
    );

    return {
      statusCode: 200,
      body: JSON.stringify(result.Items ?? []),
    };
  }

  return {
    statusCode: 200,
    body: JSON.stringify({ message: "pendiente" }),
  };
};
