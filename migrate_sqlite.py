import sqlite3
import shutil
import os
import datetime

# 1. Locate and verify exact database path
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, 'instance', 'developer_productivity.db')

print(f"Target SQLite database: {db_path}")
if not os.path.exists(db_path):
    raise FileNotFoundError(f"Database not found at {db_path}")

# 2. Create timestamped backup of the database
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = f"{db_path}.backup_{timestamp}"
shutil.copy2(db_path, backup_path)
print(f"Backup created at: {backup_path}")

# 3. Connect to database
con = sqlite3.connect(db_path)
cur = con.cursor()

# Verify pre-migration state
cur.execute("PRAGMA table_info(users)")
pre_cols = cur.fetchall()
print("\n--- Pre-Migration PRAGMA table_info(users) ---")
for col in pre_cols:
    print(col)
# Column structure: (cid, name, type, notnull, dflt_value, pk)
# Index 3 is 'notnull'

cur.execute("SELECT COUNT(*) FROM users")
pre_user_count = cur.fetchone()[0]
print(f"Pre-migration user count: {pre_user_count}")

cur.execute("SELECT id, email, role, firebase_uid, password_hash IS NOT NULL FROM users")
pre_users = cur.fetchall()
print("Pre-migration users:")
for u in pre_users:
    print(u)

# 4. Perform SQLite table-rebuild migration with foreign keys disabled
try:
    # Disable foreign keys during table restructuring
    cur.execute("PRAGMA foreign_keys = OFF")
    cur.execute("BEGIN TRANSACTION")

    # Create temporary table new_users with firebase_uid as nullable
    cur.execute("""
    CREATE TABLE new_users (
        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        firebase_uid VARCHAR(128) NULL,
        email VARCHAR(150) NOT NULL,
        full_name VARCHAR(150) NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT 'developer',
        photo_url VARCHAR(300) NULL,
        department VARCHAR(100) NULL DEFAULT 'Engineering',
        bio TEXT NULL,
        phone_number VARCHAR(30) NULL,
        is_active BOOLEAN NULL DEFAULT 1,
        created_at DATETIME NULL,
        last_login DATETIME NULL,
        password_hash VARCHAR(255) NULL
    );
    """)

    # Copy all data from users to new_users
    # Explicitly map all columns
    cur.execute("""
    INSERT INTO new_users (
        id, firebase_uid, email, full_name, role, photo_url,
        department, bio, phone_number, is_active, created_at,
        last_login, password_hash
    )
    SELECT 
        id, firebase_uid, email, full_name, role, photo_url,
        department, bio, phone_number, is_active, created_at,
        last_login, password_hash
    FROM users;
    """)

    # Drop original table
    cur.execute("DROP TABLE users")

    # Rename new_users to users
    cur.execute("ALTER TABLE new_users RENAME TO users")

    # Recreate all indexes
    cur.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")
    cur.execute("CREATE UNIQUE INDEX ix_users_firebase_uid ON users (firebase_uid)")

    # Re-enable foreign keys and commit
    cur.execute("PRAGMA foreign_keys = ON")
    con.commit()
    print("\nMigration transaction committed successfully.")

except Exception as e:
    con.rollback()
    print(f"Error during migration: {e}")
    # Restore from backup
    con.close()
    shutil.copy2(backup_path, db_path)
    raise

# 5. Verify post-migration state
cur.execute("PRAGMA table_info(users)")
post_cols = cur.fetchall()
print("\n--- Post-Migration PRAGMA table_info(users) ---")
firebase_uid_col = None
for col in post_cols:
    print(col)
    if col[1] == 'firebase_uid':
        firebase_uid_col = col

print("\n--- Indexes on users ---")
for idx in cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='users'").fetchall():
    print(idx)

cur.execute("SELECT COUNT(*) FROM users")
post_user_count = cur.fetchone()[0]
print(f"\nPost-migration user count: {post_user_count}")
assert post_user_count == pre_user_count, f"User count mismatch: {post_user_count} vs {pre_user_count}"

cur.execute("SELECT id, email, role, firebase_uid, password_hash IS NOT NULL FROM users")
post_users = cur.fetchall()
for u in post_users:
    print(u)

# Check foreign key integrity
cur.execute("PRAGMA foreign_keys = ON")
fk_errors = cur.execute("PRAGMA foreign_key_check").fetchall()
print(f"Foreign key check errors count: {len(fk_errors)}")

con.close()

if firebase_uid_col and firebase_uid_col[3] == 0:
    print("\n>>> SUCCESS: firebase_uid NOT NULL constraint successfully removed (notnull = 0)!")
else:
    print("\n>>> FAILURE: firebase_uid still has NOT NULL constraint!")
