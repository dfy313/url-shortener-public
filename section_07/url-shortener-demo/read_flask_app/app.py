from flask import Flask, jsonify, make_response
import pymysql
import redis

app = Flask(__name__)

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

@app.route('/url/<short_key>', methods=['GET'])
def handle_read(short_key):
    print(f"READ REQUEST FOR SHORT KEY: {short_key}")
    if not short_key:
        return jsonify({"message": "'shortKey' is required."}), 400

    r = get_redis_client()
    cached = True

    try:
        long_url = r.hget("url_shortener:shortKey_cache", short_key)
    except redis.RedisError as e:
        return jsonify({"message": "Redis error", "error": str(e)}), 500

    if not long_url:
        cached = False
        try:
            long_url = fetch_long_url(short_key)
            if not long_url:
                # Flask Convention
                return jsonify({"message": "Short URL not found."}), 404
            r.hset("url_shortener:shortKey_cache", short_key, long_url)
        except pymysql.MySQLError as e:
            # Flask Convention
            return jsonify({"message": f"Database error: {str(e)}"}), 500

    return make_response(
        jsonify(short_key=short_key, long_url=long_url, cached=cached),
        302,
        {"Location": long_url}
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
