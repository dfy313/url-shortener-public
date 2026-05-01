import pymysql
import json
import redis
from sqids import Sqids

"""
POST <endpoint_name>/url
{
    longUrl: <REQUIRED long url> 
    shortKey: <Optional custom alias>
    expirationTime: <Optional expiration time>
}
"""

def get_redis_client():
    """REDIS_CONNECTION_STRING=redis://default:<password>@<host>:<port>"""
    return redis.StrictRedis(
        host='<YOUR_REDIS_HOST>',
        port='<YOUR_REDIS_PORT>',
        password='<YOUR_REDIS_PASSWORD>',
        decode_responses=True
    )

def generate_short_key_with_redis(r):
    # Generate a unique short key using Redis and Sqids
    sqids_instance = Sqids(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_length=6)
    while True:
        counter = r.incr("url_shortener:counter")
        short_key = sqids_instance.encode([counter])
        if not r.sismember("url_shortener:custom_aliases", short_key):
            return short_key

def get_write_db_connection_cursor():
    conn = pymysql.connect(
        host="<PASTE_YOUR_RDS_ENDPOINT_HERE>",
        user="admin",
        password="Password100!",
        database="urls_db"
    )
    return conn, conn.cursor()

def insert_url(user_id, short_key, long_url, expiration_time, custom_alias):
    conn, cursor = get_write_db_connection_cursor()
    try:
        insert_query = """
            INSERT INTO Urls (user_id, shortKey, longUrl, expirationTime, customAlias)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (user_id, short_key, long_url, expiration_time, custom_alias))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def lambda_handler(event, context):
    user_id = "user_123" # hardcoded, user auth & handling out of scope
    r = get_redis_client()

    try:
        event_body = json.loads(event["body"])
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"message": str(e)})}

    long_url = event_body.get("longUrl")
    if not long_url:
        return {"statusCode": 400, "body": json.dumps({"message": "'longUrl' is required."})}

    short_key = event_body.get("shortKey")
    custom_alias = short_key is not None

    if custom_alias:
        if r.sismember("url_shortener:custom_aliases", short_key):
            return {"statusCode": 400, "body": json.dumps({"message": "Custom alias already in use."})}
    else:
        short_key = generate_short_key_with_redis(r)

    expiration_time = event_body.get("expirationTime")

    try:
        insert_url(user_id, short_key, long_url, expiration_time, custom_alias)

        if custom_alias:
            r.sadd("url_shortener:custom_aliases", short_key)

    except pymysql.err.IntegrityError as e:
        # Conflict / integrity violation
        return {"statusCode": 409, "body": json.dumps({"message": f"Database integrity error: {str(e)}"})}

    except pymysql.MySQLError as e:
        # General DB server error
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "shortKey": short_key,
            "longUrl": long_url,
            "expirationTime": expiration_time if expiration_time else None,
            "customAlias": custom_alias
        })
    }


if __name__ == "__main__":
    event = {
        "body": json.dumps({
            "longUrl": "https://excalidraw.com/",      # REQUIRED
            # "shortKey": "xyz321",                      # Optional
            # "expirationTime": "2030-04-01T23:59:59Z"   # Optional
        }),
    }
    res = lambda_handler(event, None)
    print(res)
 