#!/bin/bash
set -e

echo "🐳 Cricket Commentary System - Docker Entrypoint"
echo "================================================"

# Wait for MySQL to be ready
echo "⏳ Waiting for MySQL to be ready..."
while ! mysqladmin ping -h"${MYSQL_HOST}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" --silent; do
    sleep 1
done
echo "✅ MySQL is ready!"

# Check if DeliveryAudio table exists, create if not
echo "🔍 Checking database schema..."
python3 - <<EOF
import pymysql
import os
import time

# Retry connection
for i in range(5):
    try:
        conn = pymysql.connect(
            host=os.getenv('MYSQL_HOST'),
            port=int(os.getenv('MYSQL_PORT', '3306')),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD'),
            database=os.getenv('MYSQL_DATABASE'),
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        
        # Check if DeliveryAudio table exists
        cursor.execute("SHOW TABLES LIKE 'DeliveryAudio'")
        if not cursor.fetchone():
            print("📝 Creating DeliveryAudio table...")
            with open('create_audio_table.sql', 'r') as f:
                # Execute SQL (simplified, assumes single statement)
                cursor.execute(f.read())
            conn.commit()
            print("✅ DeliveryAudio table created")
        else:
            print("✅ DeliveryAudio table exists")
        
        cursor.close()
        conn.close()
        break
    except Exception as e:
        print(f"⚠️  Attempt {i+1}/5 failed: {e}")
        time.sleep(2)
EOF

echo ""
echo "🚀 Starting Cricket Commentator..."
echo "================================================"

# Execute the main command
exec "$@"
