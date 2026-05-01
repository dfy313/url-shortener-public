import pymysql
import json

"""
GET <endpoint_name>/url/{shortKey}  →   longUrl
"""

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
    short_key = event["pathParameters"]["shortKey"]

    if not short_key:
        return {"statusCode": 400, "body": "Error: 'shortKey' is required."}

    try:
        long_url = fetch_long_url(short_key)
        if not long_url:
            return {"statusCode": 404, "body": json.dumps({"message": "Long URL for the provided shortKey not found."})}

    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}
    
    return {
        "statusCode": 200, # TODO: change to redirect status code
        "headers": {"Location": long_url.decode() if isinstance(long_url, bytes) else long_url},
        "body": json.dumps({
            "short_key": short_key,
            "long_url": long_url.decode() if isinstance(long_url, bytes) else long_url,
        })
    }


if __name__ == "__main__":
    event = {
        "pathParameters": {
            "shortKey": "xyz321"
        }
    }
    res = lambda_handler(event, None)
    print(res)
