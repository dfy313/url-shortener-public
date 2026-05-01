import pymysql
import json
import random

"""
POST <endpoint_name>/url
{
    longUrl: <REQUIRED long url> 
    shortKey: <Optional custom alias>
    expirationTime: <Optional expiration time>
}
"""

def generate_short_key(length=6):
    # For now, if this results in a collision, the DB will throw an error, and the user will have to try again.
    # Same goes for the custom alias.
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(random.choices(characters, k=length))

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

    try:
        event_body = json.loads(event["body"])
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"message": str(e)})}

    long_url = event_body.get("longUrl")
    if not long_url:
        return {"statusCode": 400, "body": json.dumps({"message": "'longUrl' is required."})}

    # If shortKey is provided, use that. Otherwise, need to generate.
    short_key = event_body.get("shortKey") or generate_short_key()
    custom_alias = "shortKey" in event_body
    expiration_time = event_body.get("expirationTime")

    try:
        insert_url(user_id, short_key, long_url, expiration_time, custom_alias)

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
            "shortKey": "custom",                      # Optional
            "expirationTime": "2030-04-01T23:59:59Z"   # Optional
        }),
    }
    res = lambda_handler(event, None)
    print(res)
 