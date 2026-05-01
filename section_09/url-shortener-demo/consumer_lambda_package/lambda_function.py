import base64
import json
import redis

def get_redis_client():
    """REDIS_CONNECTION_STRING=redis://default:<password>@<host>:<port>"""
    return redis.StrictRedis(
        host='<YOUR_REDIS_HOST>',
        port='<YOUR_REDIS_PORT>',
        password='<YOUR_REDIS_PASSWORD>',
        decode_responses=True
    )

def lambda_handler(event, context):
    r = get_redis_client()

    for record in event["Records"]:
        try:
            # Decode and parse record from Kinesis
            kinesis_data = base64.b64decode(record["kinesis"]["data"]).decode("utf-8")
            payload = json.loads(kinesis_data)

            if payload["metadata"]["operation"] != "insert":
                continue  # Ignore updates/deletes

            short_key = payload["data"]["shortKey"]
            long_url = payload["data"]["longUrl"]

            r.hset("url_shortener:shortKey_cache", short_key, long_url)
            print(f"✅ Cached {short_key} → {long_url}")

        except Exception as e:
            print(f"⚠️ Error processing record: {e}")


if __name__ == "__main__":
    sample_payload = {
        "data": {
            "user_id": "user_123",
            "shortKey": "SAMPLE",
            "longUrl": "https://www.chatgpt.com/",
            "expirationTime": "2030-04-01T23:59:59Z",
            "createdAt": "2025-04-10T17:33:21Z",
            "customAlias": 1
        },
        "metadata": {
            "timestamp": "2025-04-10T17:33:26.412037Z",
            "record-type": "data",
            "operation": "insert",
            "partition-key-type": "schema-table",
            "schema-name": "urls_db",
            "table-name": "Urls",
            "transaction-id": 12403865551447
        }
    }

    event = {
        "Records": [
            {
                "kinesis": {
                    "data": base64.b64encode(json.dumps(sample_payload).encode("utf-8")).decode("utf-8")
                }
            }
        ]
    }

    lambda_handler(event, None)