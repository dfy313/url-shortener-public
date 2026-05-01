# 📺 Url Shortener – Section 1

Welcome! This section contains the setup instructions and demo walkthrough for building the initial foundation of the URL Shortener project — including setting up the **MySQL database** and creating the initial `Urls` table.

<div align="center">
    <img src="./section_1_design.png" alt="System Architecture Diagram" width="500"/>
</div>

## 🎥 Video Walkthrough

**Title:** Url Shortener – Section 1  
**Link:** [Watch on Udemy](https://www.udemy.com)

# ⚙️ Instructions and Commands

### 1. Connect to MySQL Instance Remotely

Launch a MySQL container:

```bash
docker run -it --rm mysql:latest bash
```

Connect to your RDS MySQL database:

```bash
mysql -h <PASTE_YOUR_RDS_ENDPOINT_HERE> -u admin -p
```

> _When prompted, enter the database password:_ `Password100!`

Confirm that the `urls_db` database is visible:

```bash
SHOW DATABASES;
```

Switch to the `urls_db` database:

```bash
USE urls_db;
```

Verify that no tables currently exist:

```bash
SHOW TABLES;
```

### 2. Set Up the Urls Table

Create the `Urls` table to store shortened links:

```bash
CREATE TABLE Urls (
    user_id VARCHAR(255) NOT NULL,
    shortKey VARCHAR(255) NOT NULL PRIMARY KEY,
    longUrl TEXT NOT NULL,
    expirationTime DATETIME NULL,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    customAlias BOOLEAN DEFAULT FALSE
);
```

Verify that the table was created:

```bash
SHOW TABLES;
```

Confirm that the table is currently empty:

```bash
SELECT * FROM Urls;
```

### 3. Seed Initial Records into Urls Table

Insert a basic record:

```bash
INSERT INTO Urls (user_id, shortKey, longUrl, customAlias)
VALUES ('user_123', 'abc123', 'https://google.com', FALSE);
```

Insert another record with an expiration time:

```bash
INSERT INTO Urls (user_id, shortKey, longUrl, expirationTime, customAlias)
VALUES (
    'user_123',
    'xyz321',
    'https://wikipedia.com',
    DATE_ADD(NOW(), INTERVAL 30 DAY),
    FALSE
);
```

Confirm that the records were created:

```bash
SELECT * FROM Urls;
```

<br>
