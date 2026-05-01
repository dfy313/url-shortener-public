import pymysql
import json
import redis

"""
GET <endpoint_name>/url/{shortKey}  →   longUrl
"""

def get_redis_client():
    """REDIS_CONNECTION_STRING=redis://default:<password>@<host>:<port>"""
    return redis.StrictRedis(
        host='<YOUR_REDIS_HOST>',
        port='<YOUR_REDIS_PORT>',
        password='<YOUR_REDIS_PASSWORD>',
        decode_responses=True
    )

def get_read_db_connection_cursor():
    conn = pymysql.connect(
        host="<PASTE_YOUR_RDS_ENDPOINT_HERE>",
        user="admin",
        password="Password100!",
        database="urls_db",
    )
    return conn, conn.cursor()

def fetch_long_url(short_key):
    conn, cursor = get_read_db_connection_cursor()
    try:
        cursor.execute("SELECT longUrl FROM Urls WHERE shortKey = %s", (short_key))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()
        conn.close()

def lambda_handler(event, context):
    print("READ EVENT: ", event)
    print("READ CONTEXT: ", context)

    short_key = event["pathParameters"]["shortKey"]
    if not short_key:
        return {"statusCode": 400, "body": "Error: 'shortKey' is required."}

    r = get_redis_client()
    cached = True

    try:
        # Attempt to fetch from Redis hash
        long_url = r.hget("url_shortener:shortKey_cache", short_key)
    except redis.RedisError as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Redis error", "error": str(e)})
        }

    # If not in Redis, hit the database and cache the result
    if not long_url:
        cached = False
        try:
            long_url = fetch_long_url(short_key)
            if not long_url:
                return {"statusCode": 404, "body": json.dumps({"message": "Long URL for the provided shortKey not found."})}
            
            # Cache the result in Redis
            r.hset("url_shortener:shortKey_cache", short_key, long_url)

        except pymysql.MySQLError as e:
            return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}

    return {
        "statusCode": 302,
        "headers": {"Location": long_url.decode() if isinstance(long_url, bytes) else long_url},
        "body": json.dumps({
            "short_key": short_key,
            "long_url": long_url.decode() if isinstance(long_url, bytes) else long_url,
            "cached": cached
        })
    }


if __name__ == "__main__":
    event = {
        "pathParameters": {
            "shortKey": "abc123"
        }
    }
    res = lambda_handler(event, None)
    print(res)
