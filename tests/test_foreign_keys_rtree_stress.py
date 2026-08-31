"""Comprehensive stress tests for Foreign Keys, R*Tree virtual shadow tables, PRAGMA invariants, and escaped identifiers."""

import os
import sqlite3
import pytest
from fastmcp_sqlite.engine import SQLiteEngine


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def fk_test_db(tmp_path) -> str:
    """Create a database with complex Foreign Key hierarchies."""
    db_file = tmp_path / "test_fk_stress.db"
    db_path = str(db_file)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    # 1. Departments -> Employees -> Tasks (Cascade chain)
    cur.execute("""
        CREATE TABLE departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_name TEXT UNIQUE NOT NULL
        );
    """)

    cur.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_id INTEGER NOT NULL,
            emp_name TEXT NOT NULL,
            salary REAL DEFAULT 50000.0,
            FOREIGN KEY (dept_id) REFERENCES departments(id) ON DELETE CASCADE ON UPDATE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            FOREIGN KEY (emp_id) REFERENCES employees(id) ON DELETE CASCADE ON UPDATE CASCADE
        );
    """)

    # 2. Categories -> Products with ON DELETE RESTRICT
    cur.execute("""
        CREATE TABLE categories (
            code TEXT PRIMARY KEY,
            label TEXT NOT NULL
        );
    """)

    cur.execute("""
        CREATE TABLE products (
            sku TEXT PRIMARY KEY,
            cat_code TEXT NOT NULL,
            title TEXT NOT NULL,
            FOREIGN KEY (cat_code) REFERENCES categories(code) ON DELETE RESTRICT ON UPDATE CASCADE
        );
    """)

    # 3. Self-referencing tree hierarchy with CASCADE
    cur.execute("""
        CREATE TABLE org_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            node_name TEXT NOT NULL,
            FOREIGN KEY (parent_id) REFERENCES org_nodes(id) ON DELETE CASCADE
        );
    """)

    # 4. Composite Foreign Key
    cur.execute("""
        CREATE TABLE branch_locations (
            company_id INTEGER NOT NULL,
            branch_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            PRIMARY KEY (company_id, branch_id)
        );
    """)

    cur.execute("""
        CREATE TABLE inventory_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            branch_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 0,
            FOREIGN KEY (company_id, branch_id) REFERENCES branch_locations(company_id, branch_id) ON DELETE CASCADE
        );
    """)

    # Seed initial data
    cur.execute("INSERT INTO departments (dept_name) VALUES ('Engineering'), ('Marketing');")
    cur.execute("INSERT INTO employees (dept_id, emp_name) VALUES (1, 'Alice'), (1, 'Bob'), (2, 'Charlie');")
    cur.execute("INSERT INTO tasks (emp_id, task_name) VALUES (1, 'Build Kernel'), (1, 'Fix Bug'), (2, 'Write Docs'), (3, 'Run Ads');")

    cur.execute("INSERT INTO categories (code, label) VALUES ('ELEC', 'Electronics'), ('BOOK', 'Books');")
    cur.execute("INSERT INTO products (sku, cat_code, title) VALUES ('LAP-01', 'ELEC', 'Laptop Pro'), ('NOV-01', 'BOOK', 'SciFi Novel');")

    cur.execute("INSERT INTO org_nodes (id, parent_id, node_name) VALUES (1, NULL, 'Root CEO');")
    cur.execute("INSERT INTO org_nodes (id, parent_id, node_name) VALUES (2, 1, 'VP Engineering');")
    cur.execute("INSERT INTO org_nodes (id, parent_id, node_name) VALUES (3, 2, 'Tech Lead');")
    cur.execute("INSERT INTO org_nodes (id, parent_id, node_name) VALUES (4, 3, 'Senior Engineer');")

    cur.execute("INSERT INTO branch_locations (company_id, branch_id, address) VALUES (100, 1, '100 Main St'), (100, 2, '200 Oak Ave');")
    cur.execute("INSERT INTO inventory_items (company_id, branch_id, item_name, quantity) VALUES (100, 1, 'Server Rack', 5), (100, 2, 'Switch', 10);")

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def rtree_stress_db(tmp_path) -> str:
    """Create a database with multiple R*Tree virtual tables and potentially conflicting user tables."""
    db_file = tmp_path / "test_rtree_stress.db"
    db_path = str(db_file)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Create R*Tree virtual tables (2D and 3D)
    cur.execute("CREATE VIRTUAL TABLE geo USING rtree(id, minX, maxX, minY, maxY);")
    cur.execute("CREATE VIRTUAL TABLE spatial_3d USING rtree(id, minX, maxX, minY, maxY, minZ, maxZ);")

    # Insert sample bounding boxes
    cur.execute("INSERT INTO geo VALUES (1, -122.5, -122.3, 37.7, 37.9);")
    cur.execute("INSERT INTO geo VALUES (2, -74.1, -73.9, 40.6, 40.8);")
    cur.execute("INSERT INTO spatial_3d VALUES (10, 0.0, 10.0, 0.0, 10.0, 0.0, 10.0);")

    # Create legitimate user tables that contain shadow suffixes (_node, _rowid, _parent, _data, etc.)
    cur.execute("CREATE TABLE user_node (id INTEGER PRIMARY KEY, node_title TEXT);")
    cur.execute("CREATE TABLE task_parent (id INTEGER PRIMARY KEY, parent_ref TEXT);")
    cur.execute("CREATE TABLE event_rowid (id INTEGER PRIMARY KEY, rowid_val INTEGER);")
    cur.execute("CREATE TABLE geo_extra (id INTEGER PRIMARY KEY, meta_desc TEXT);")
    cur.execute("CREATE TABLE spatial_3d_backup (id INTEGER PRIMARY KEY, bkp_name TEXT);")

    cur.execute("INSERT INTO user_node VALUES (1, 'Master Node');")
    cur.execute("INSERT INTO task_parent VALUES (1, 'Epic Parent');")
    cur.execute("INSERT INTO event_rowid VALUES (1, 9999);")
    cur.execute("INSERT INTO geo_extra VALUES (1, 'Extra Geo Metadata');")
    cur.execute("INSERT INTO spatial_3d_backup VALUES (1, 'Full 3D Backup');")

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def special_chars_db(tmp_path) -> str:
    """Create a database with unusual, quoted, and unicode table and column names."""
    db_file = tmp_path / "test_special_names.db"
    db_path = str(db_file)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    # Table with double quotes in name
    cur.execute("""
        CREATE TABLE "tbl""quotes" (
            "id" INTEGER PRIMARY KEY,
            "col""val" TEXT
        );
    """)

    # Table with spaces, brackets, hyphens
    cur.execute("""
        CREATE TABLE "user [special] (table)-2026" (
            "user id" INTEGER PRIMARY KEY,
            "full name" TEXT NOT NULL,
            "email address" TEXT
        );
    """)

    # Table with Vietnamese Unicode characters
    cur.execute("""
        CREATE TABLE "bảng_dữ_liệu_khách_hàng" (
            "mã_khách" INTEGER PRIMARY KEY AUTOINCREMENT,
            "họ_và_tên" TEXT NOT NULL,
            "số_điện_thoại" TEXT
        );
    """)

    # Table with dots and symbols
    cur.execute("""
        CREATE TABLE "schema.v1.table#metrics" (
            "metric.key" TEXT PRIMARY KEY,
            "metric.value" REAL
        );
    """)

    # Foreign key referencing table with quotes
    cur.execute("""
        CREATE TABLE "tbl""child" (
            "child_id" INTEGER PRIMARY KEY,
            "parent_id" INTEGER,
            FOREIGN KEY ("parent_id") REFERENCES "tbl""quotes"("id") ON DELETE CASCADE
        );
    """)

    # Seed data
    cur.execute('INSERT INTO "tbl""quotes" ("id", "col""val") VALUES (1, \'Sample "quoted" value\');')
    cur.execute('INSERT INTO "tbl""child" ("child_id", "parent_id") VALUES (101, 1);')
    cur.execute('INSERT INTO "user [special] (table)-2026" ("user id", "full name", "email address") VALUES (1, \'Jane Doe\', \'jane@test.org\');')
    cur.execute('INSERT INTO "bảng_dữ_liệu_khách_hàng" ("họ_và_tên", "số_điện_thoại") VALUES (\'Nguyễn Văn A\', \'0901234567\');')
    cur.execute('INSERT INTO "schema.v1.table#metrics" ("metric.key", "metric.value") VALUES (\'cpu_usage\', 42.5);')

    # Index on table with special name
    cur.execute('CREATE INDEX "idx_spec""name" ON "tbl""quotes"("col""val");')

    conn.commit()
    conn.close()
    return db_path


# ============================================================================
# 1. Foreign Key Stress Tests
# ============================================================================

def test_fk_pragma_active_on_all_connections(fk_test_db):
    """Ensure PRAGMA foreign_keys is strictly ON on every connection created by SQLiteEngine."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=False)

    # Test read-write connection
    conn_rw = engine.get_connection(fk_test_db, readonly=False)
    cur = conn_rw.cursor()
    cur.execute("PRAGMA foreign_keys;")
    assert cur.fetchone()[0] == 1
    conn_rw.close()

    # Test read-only connection
    conn_ro = engine.get_connection(fk_test_db, readonly=True)
    cur = conn_ro.cursor()
    cur.execute("PRAGMA foreign_keys;")
    assert cur.fetchone()[0] == 1
    conn_ro.close()

    # Test in-memory connection
    mem_engine = SQLiteEngine(default_db=":memory:", readonly=False)
    conn_mem = mem_engine.get_connection(":memory:", readonly=False)
    cur = conn_mem.cursor()
    cur.execute("PRAGMA foreign_keys;")
    assert cur.fetchone()[0] == 1
    conn_mem.close()


def test_fk_insert_violation_rejection(fk_test_db):
    """Test inserting child record referencing non-existent parent fails with foreign key violation."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=False)

    # Valid insert succeeds
    valid_res = engine.execute_query(
        "INSERT INTO employees (dept_id, emp_name) VALUES (1, 'Diana');",
        readonly=False,
    )
    assert "Query executed successfully" in valid_res
    assert "Rows affected: 1" in valid_res

    # Insert referencing invalid dept_id=999 must fail
    invalid_res = engine.execute_query(
        "INSERT INTO employees (dept_id, emp_name) VALUES (999, 'Ghost Employee');",
        readonly=False,
    )
    assert "FOREIGN KEY constraint failed" in invalid_res

    # Verify invalid record was NOT inserted
    check_res = engine.execute_query("SELECT count(*) FROM employees WHERE emp_name = 'Ghost Employee';")
    assert "**Rows Returned:** 1" in check_res
    assert "| 0 |" in check_res


def test_fk_delete_cascade_deep_hierarchy(fk_test_db):
    """Test deleting parent record cascades down to children (employees) and grandchildren (tasks)."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=False)

    # Prior to delete: Engineering (id=1) has 2 employees (Alice, Bob) and 3 tasks
    cur_tasks = engine.execute_query("SELECT count(*) FROM tasks;")
    assert "| 4 |" in cur_tasks

    # Delete department id=1 (Engineering)
    del_res = engine.execute_query(
        "DELETE FROM departments WHERE id = 1 RETURNING id, dept_name;",
        readonly=False,
        format="json",
    )
    assert "Engineering" in del_res

    # Verify employees of Engineering (Alice, Bob) are cascade-deleted
    emp_res = engine.execute_query("SELECT emp_name FROM employees;")
    assert "Alice" not in emp_res
    assert "Bob" not in emp_res
    assert "Charlie" in emp_res  # Charlie is in Marketing (id=2), untouched

    # Verify tasks of Engineering employees are cascade-deleted (only Charlie's task remains)
    task_res = engine.execute_query("SELECT task_name FROM tasks;")
    assert "Build Kernel" not in task_res
    assert "Fix Bug" not in task_res
    assert "Write Docs" not in task_res
    assert "Run Ads" in task_res


def test_fk_on_delete_restrict(fk_test_db):
    """Test ON DELETE RESTRICT prevents deleting category while products reference it."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=False)

    # Attempt to delete ELEC category which has product Laptop Pro
    res = engine.execute_query("DELETE FROM categories WHERE code = 'ELEC';", readonly=False)
    assert "FOREIGN KEY constraint failed" in res

    # Verify ELEC category is still intact
    cat_check = engine.execute_query("SELECT label FROM categories WHERE code = 'ELEC';")
    assert "Electronics" in cat_check

    # Delete product first, then deleting category must succeed
    engine.execute_query("DELETE FROM products WHERE cat_code = 'ELEC';", readonly=False)
    success_del = engine.execute_query("DELETE FROM categories WHERE code = 'ELEC';", readonly=False)
    assert "Query executed successfully" in success_del


def test_fk_on_update_cascade_and_restrict(fk_test_db):
    """Test ON UPDATE CASCADE propagates key changes, while updating child to non-existent key fails."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=False)

    # Update category code 'BOOK' -> 'LITERATURE'
    update_res = engine.execute_query(
        "UPDATE categories SET code = 'LITERATURE' WHERE code = 'BOOK' RETURNING code, label;",
        readonly=False,
        format="json",
    )
    assert "LITERATURE" in update_res

    # Product cat_code must cascade to 'LITERATURE'
    prod_res = engine.execute_query("SELECT cat_code, title FROM products WHERE sku = 'NOV-01';")
    assert "LITERATURE" in prod_res

    # Attempt updating product cat_code to non-existent 'FOOD' must fail
    invalid_upd = engine.execute_query(
        "UPDATE products SET cat_code = 'FOOD' WHERE sku = 'NOV-01';",
        readonly=False,
    )
    assert "FOREIGN KEY constraint failed" in invalid_upd


def test_fk_self_referencing_cascade(fk_test_db):
    """Test self-referencing tree structure with cascading delete."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=False)

    # Tree: 1 (Root) -> 2 (VP) -> 3 (Lead) -> 4 (Senior)
    # Deleting node 2 (VP) should cascade delete nodes 3 and 4
    del_res = engine.execute_query(
        "DELETE FROM org_nodes WHERE id = 2 RETURNING id, node_name;",
        readonly=False,
    )
    assert "VP Engineering" in del_res

    nodes = engine.execute_query("SELECT id, node_name FROM org_nodes ORDER BY id ASC;")
    assert "Root CEO" in nodes
    assert "VP Engineering" not in nodes
    assert "Tech Lead" not in nodes
    assert "Senior Engineer" not in nodes


def test_fk_composite_key_enforcement(fk_test_db):
    """Test multi-column (composite) foreign key enforcement."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=False)

    # Valid composite insert
    res_valid = engine.execute_query(
        "INSERT INTO inventory_items (company_id, branch_id, item_name, quantity) VALUES (100, 1, 'Router', 3);",
        readonly=False,
    )
    assert "Query executed successfully" in res_valid

    # Invalid composite insert: company_id 100 with non-existent branch_id 999
    res_invalid = engine.execute_query(
        "INSERT INTO inventory_items (company_id, branch_id, item_name, quantity) VALUES (100, 999, 'Bad Item', 1);",
        readonly=False,
    )
    assert "FOREIGN KEY constraint failed" in res_invalid

    # Cascade delete on composite key
    engine.execute_query("DELETE FROM branch_locations WHERE company_id = 100 AND branch_id = 1;", readonly=False)
    items_check = engine.execute_query("SELECT item_name FROM inventory_items WHERE company_id = 100 AND branch_id = 1;")
    assert "Server Rack" not in items_check
    assert "Router" not in items_check


def test_fk_transaction_automatic_rollback_on_violation(fk_test_db):
    """Ensure that on foreign key failure, the transaction is rolled back cleanly without leaving dirty state."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=False)

    # Check baseline count
    initial_cnt = engine.execute_query("SELECT count(*) FROM employees;")

    # Execute statement that violates FK
    err = engine.execute_query(
        "INSERT INTO employees (dept_id, emp_name) VALUES (404, 'Failed Transaction Emp');",
        readonly=False,
    )
    assert "FOREIGN KEY constraint failed" in err

    # Ensure count remains unchanged (3 employees)
    after_cnt = engine.execute_query("SELECT count(*) FROM employees;")
    assert "| 3 |" in after_cnt

    # Ensure subsequent write query executes normally without lock or uncommitted state
    next_insert = engine.execute_query(
        "INSERT INTO departments (dept_name) VALUES ('Human Resources') RETURNING id, dept_name;",
        readonly=False,
    )
    assert "Human Resources" in next_insert


# ============================================================================
# 2. R*Tree Virtual Table & Shadow Table Filtering Tests
# ============================================================================

def test_rtree_shadow_tables_fully_hidden_in_describe_schema(rtree_stress_db):
    """Verify describe_schema hides R*Tree shadow tables (geo_node, geo_rowid, geo_parent) while keeping user tables."""
    engine = SQLiteEngine(default_db=rtree_stress_db)
    schema_doc = engine.describe_schema()

    # R*Tree virtual tables must be present
    assert "`geo`" in schema_doc
    assert "`spatial_3d`" in schema_doc

    # R*Tree shadow tables must be completely excluded
    assert "geo_node" not in schema_doc
    assert "geo_rowid" not in schema_doc
    assert "geo_parent" not in schema_doc
    assert "spatial_3d_node" not in schema_doc
    assert "spatial_3d_rowid" not in schema_doc
    assert "spatial_3d_parent" not in schema_doc

    # Legitimate user tables with _node, _parent, _rowid must be preserved
    assert "`user_node`" in schema_doc
    assert "`task_parent`" in schema_doc
    assert "`event_rowid`" in schema_doc
    assert "`geo_extra`" in schema_doc
    assert "`spatial_3d_backup`" in schema_doc


def test_rtree_describe_table_inspection(rtree_stress_db):
    """Verify describe_table inspects R*Tree virtual table columns and DDL accurately."""
    engine = SQLiteEngine(default_db=rtree_stress_db)
    table_doc = engine.describe_table("geo")

    assert "# Table Info: `geo` (TABLE)" in table_doc
    assert "`id`" in table_doc
    assert "`minX`" in table_doc
    assert "`maxX`" in table_doc
    assert "`minY`" in table_doc
    assert "`maxY`" in table_doc
    assert "CREATE VIRTUAL TABLE geo USING rtree" in table_doc


def test_rtree_query_and_dml_returning(rtree_stress_db):
    """Test bounding box queries and DML RETURNING on R*Tree virtual tables."""
    engine = SQLiteEngine(default_db=rtree_stress_db, readonly=False)

    # Spatial range query
    query_sql = "SELECT id, minX, maxX, minY, maxY FROM geo WHERE minX >= -125.0 AND maxX <= -120.0;"
    res = engine.execute_query(query_sql, format="json")
    assert '"id": 1' in res
    assert '"id": 2' not in res  # NYC box excluded

    # Insert new bounding box
    insert_sql = "INSERT INTO geo (id, minX, maxX, minY, maxY) VALUES (3, 10.0, 20.0, 10.0, 20.0);"
    res_ins = engine.execute_query(insert_sql, readonly=False)
    assert "Query executed successfully" in res_ins

    # Verify inserted box
    verify_res = engine.execute_query("SELECT id FROM geo WHERE id = 3;")
    assert "| 3 |" in verify_res

    # Delete from R*Tree
    del_res = engine.execute_query("DELETE FROM geo WHERE id = 3;", readonly=False)
    assert "Query executed successfully" in del_res


# ============================================================================
# 3. PRAGMA Invariants Extreme Stress Tests
# ============================================================================

def test_full_pragma_invariants(fk_test_db):
    """Verify all 8 PRAGMA settings on every connection opened by SQLiteEngine."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=False)
    conn = engine.get_connection(fk_test_db, readonly=False)
    cur = conn.cursor()

    # 1. busy_timeout = 5000
    cur.execute("PRAGMA busy_timeout;")
    assert cur.fetchone()[0] == 5000

    # 2. journal_mode = WAL
    cur.execute("PRAGMA journal_mode;")
    assert cur.fetchone()[0].upper() == "WAL"

    # 3. synchronous = NORMAL (1)
    cur.execute("PRAGMA synchronous;")
    assert cur.fetchone()[0] == 1

    # 4. mmap_size = 268435456 (256MB)
    cur.execute("PRAGMA mmap_size;")
    assert cur.fetchone()[0] == 268435456

    # 5. cache_size = -64000 (64MB page cache)
    cur.execute("PRAGMA cache_size;")
    assert cur.fetchone()[0] == -64000

    # 6. temp_store = MEMORY (2)
    cur.execute("PRAGMA temp_store;")
    assert cur.fetchone()[0] == 2

    # 7. foreign_keys = ON (1)
    cur.execute("PRAGMA foreign_keys;")
    assert cur.fetchone()[0] == 1

    # 8. query_only = OFF (0) in read-write mode
    cur.execute("PRAGMA query_only;")
    assert cur.fetchone()[0] == 0

    conn.close()


def test_readonly_mode_pragma_and_security(fk_test_db):
    """Verify readonly connection enforces query_only = ON and rejects write operations."""
    engine = SQLiteEngine(default_db=fk_test_db, readonly=True)

    # 1. PRAGMA query_only is ON on readonly connection
    conn = engine.get_connection(fk_test_db, readonly=True)
    cur = conn.cursor()
    cur.execute("PRAGMA query_only;")
    assert cur.fetchone()[0] == 1
    conn.close()

    # 2. Direct mutation statements are blocked before execution
    mutation_queries = [
        "INSERT INTO departments (dept_name) VALUES ('Forbidden')",
        "UPDATE departments SET dept_name = 'Hacked' WHERE id = 1",
        "DELETE FROM departments WHERE id = 1",
        "DROP TABLE departments",
        "ALTER TABLE departments ADD COLUMN secret TEXT",
        "CREATE TABLE hacker_tbl (id INT)",
        "/* tricky comment */ INSERT INTO departments (dept_name) VALUES ('Tricky')",
        "-- comment \n INSERT INTO departments (dept_name) VALUES ('Newline')",
    ]

    for q in mutation_queries:
        res = engine.execute_query(q)
        assert "forbidden in read-only mode" in res


# ============================================================================
# 4. Escaped Identifiers & Special Table Names Stress Tests
# ============================================================================

def test_describe_schema_with_special_table_names(special_chars_db):
    """Verify describe_schema handles double quotes, spaces, brackets, dots, and unicode table names."""
    engine = SQLiteEngine(default_db=special_chars_db)
    schema_doc = engine.describe_schema()

    # All special tables must appear in overview
    assert '`tbl"quotes`' in schema_doc
    assert '`tbl"child`' in schema_doc
    assert '`user [special] (table)-2026`' in schema_doc
    assert '`bảng_dữ_liệu_khách_hàng`' in schema_doc
    assert '`schema.v1.table#metrics`' in schema_doc

    # Prompt caching latency footer must be present at the end
    assert "*Discovery Latency:" in schema_doc
    assert schema_doc.strip().endswith("(O(1) non-blocking scan)*")


def test_describe_table_with_quotes_and_unicode(special_chars_db):
    """Verify describe_table properly introspects tables with embedded double quotes and unicode."""
    engine = SQLiteEngine(default_db=special_chars_db)

    # Table with double quotes in name
    info_quotes = engine.describe_table('tbl"quotes')
    assert '# Table Info: `tbl"quotes` (TABLE)' in info_quotes
    assert '`col"val`' in info_quotes
    assert 'idx_spec"name' in info_quotes

    # Table with Vietnamese Unicode
    info_vn = engine.describe_table('bảng_dữ_liệu_khách_hàng')
    assert '# Table Info: `bảng_dữ_liệu_khách_hàng` (TABLE)' in info_vn
    assert '`mã_khách`' in info_vn
    assert '`họ_và_tên`' in info_vn
    assert '`số_điện_thoại`' in info_vn

    # Child table with FK to quoted table
    info_child = engine.describe_table('tbl"child')
    assert '# Table Info: `tbl"child` (TABLE)' in info_child
    assert 'tbl"quotes(id)' in info_child or 'tbl"quotes' in info_child


def test_execute_query_on_special_table_names(special_chars_db):
    """Test SQL CRUD operations on tables with quotes and special characters."""
    engine = SQLiteEngine(default_db=special_chars_db, readonly=False)

    # Query table with quotes
    res_select = engine.execute_query('SELECT "col""val" FROM "tbl""quotes" WHERE "id" = 1;')
    assert 'Sample "quoted" value' in res_select

    # Insert into table with quotes RETURNING
    res_insert = engine.execute_query(
        'INSERT INTO "tbl""quotes" ("id", "col""val") VALUES (2, \'Second Quoted Row\') RETURNING "id", "col""val";',
        readonly=False,
        format="json",
    )
    assert 'Second Quoted Row' in res_insert

    # Foreign key enforcement on quoted table
    fk_fail = engine.execute_query(
        'INSERT INTO "tbl""child" ("child_id", "parent_id") VALUES (999, 404);',
        readonly=False,
    )
    assert "FOREIGN KEY constraint failed" in fk_fail

    # Foreign key cascade on quoted table
    res_del = engine.execute_query(
        'DELETE FROM "tbl""quotes" WHERE "id" = 1;',
        readonly=False,
    )
    assert "Query executed successfully" in res_del

    # Verify child record was cascade deleted
    child_check = engine.execute_query('SELECT count(*) FROM "tbl""child" WHERE "parent_id" = 1;')
    assert "| 0 |" in child_check

    # Update on Vietnamese unicode table
    res_upd = engine.execute_query(
        'UPDATE "bảng_dữ_liệu_khách_hàng" SET "số_điện_thoại" = \'0988888888\' WHERE "mã_khách" = 1 RETURNING "họ_và_tên", "số_điện_thoại";',
        readonly=False,
        format="table",
    )
    assert 'Nguyễn Văn A' in res_upd
    assert '0988888888' in res_upd
