import os
import sys
import time
import shutil
import tempfile
import sqlite3
import subprocess

def execute_python_code(code: str, timeout: int = 5) -> dict:
    """
    Executes Python code in an isolated subprocess with restricted environment.
    Applies timeout and prevents access to server secrets.
    """
    if not code or not code.strip():
        return {'status': 'success', 'output': '', 'execution_time': 0}

    py_bin = sys.executable or 'python'
    temp_dir = tempfile.mkdtemp(prefix='dpt_py_exec_')
    code_path = os.path.join(temp_dir, 'script.py')

    try:
        with open(code_path, 'w', encoding='utf-8') as f:
            f.write(code)

        clean_env = {
            'PATH': os.environ.get('PATH', ''),
            'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
            'TEMP': temp_dir,
            'TMP': temp_dir,
            'PYTHONIOENCODING': 'utf-8',
            'PYTHONUNBUFFERED': '1',
            'PYTHONHASHSEED': '0'
        }

        t0 = time.time()
        proc = subprocess.run(
            [py_bin, '-I', '-s', code_path],
            cwd=temp_dir,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed = round(time.time() - t0, 3)

        stdout = proc.stdout or ''
        stderr = proc.stderr or ''

        if proc.returncode != 0:
            err_output = (stdout + '\n' + stderr).strip() if stdout else stderr.strip()
            return {
                'status': 'error',
                'output': err_output or f'Process exited with code {proc.returncode}',
                'execution_time': elapsed,
                'exit_code': proc.returncode
            }
        else:
            out_str = stdout if stdout else (stderr if stderr else '[Process finished with code 0 - No output]')
            return {
                'status': 'success',
                'output': out_str,
                'execution_time': elapsed,
                'exit_code': 0
            }

    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'output': f'Execution timed out (limit: {timeout} seconds).',
            'execution_time': timeout,
            'timeout': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'output': f'Execution Error: {str(e)}',
            'execution_time': 0
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def execute_javascript_code(code: str, timeout: int = 5) -> dict:
    """
    Executes JavaScript code in Node.js subprocess with timeout and captured output.
    """
    if not code or not code.strip():
        return {'status': 'success', 'output': '', 'execution_time': 0}

    node_bin = shutil.which('node') or r"C:\Program Files\nodejs\node.EXE"
    if not node_bin or not os.path.exists(node_bin):
        return {
            'status': 'client_fallback',
            'output': 'Node.js runtime not found on server.',
            'fallback_to_client': True
        }

    temp_dir = tempfile.mkdtemp(prefix='dpt_js_exec_')
    code_path = os.path.join(temp_dir, 'script.js')

    try:
        with open(code_path, 'w', encoding='utf-8') as f:
            f.write(code)

        clean_env = {
            'PATH': os.environ.get('PATH', ''),
            'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
            'TEMP': temp_dir,
            'TMP': temp_dir
        }

        t0 = time.time()
        proc = subprocess.run(
            [node_bin, code_path],
            cwd=temp_dir,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed = round(time.time() - t0, 3)

        stdout = proc.stdout or ''
        stderr = proc.stderr or ''

        if proc.returncode != 0:
            err_output = (stdout + '\n' + stderr).strip() if stdout else stderr.strip()
            return {
                'status': 'error',
                'output': err_output or f'Process exited with code {proc.returncode}',
                'execution_time': elapsed,
                'exit_code': proc.returncode
            }
        else:
            out_str = stdout if stdout else (stderr if stderr else '[Process finished with code 0 - No output]')
            return {
                'status': 'success',
                'output': out_str,
                'execution_time': elapsed,
                'exit_code': 0
            }

    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'output': f'Execution timed out (limit: {timeout} seconds).',
            'execution_time': timeout,
            'timeout': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'output': f'Execution Error: {str(e)}',
            'execution_time': 0
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def split_sql_statements(sql_text: str) -> list:
    """
    Splits multi-statement SQL text safely using sqlite3.complete_statement.
    """
    statements = []
    current = []
    for line in sql_text.splitlines(True):
        current.append(line)
        candidate = "".join(current).strip()
        if candidate and sqlite3.complete_statement(candidate):
            statements.append(candidate.rstrip(";"))
            current = []
    remainder = "".join(current).strip()
    if remainder:
        statements.append(remainder.rstrip(";"))
    return [s.strip() for s in statements if s.strip()]


def format_ascii_table(columns: list, rows: list) -> str:
    """
    Formats SQL query results into a readable ASCII table.
    """
    if not columns:
        return ""
    str_rows = [[str(cell) if cell is not None else "NULL" for cell in row] for row in rows]
    widths = [len(str(col)) for col in columns]
    for row in str_rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    header_line = "| " + " | ".join(str(col).ljust(widths[i]) for i, col in enumerate(columns)) + " |"
    lines = [sep, header_line, sep]
    for row in str_rows:
        row_line = "| " + " | ".join(val.ljust(widths[i]) for i, val in enumerate(row)) + " |"
        lines.append(row_line)
    lines.append(sep)
    lines.append(f"({len(rows)} row(s) returned)")
    return "\n".join(lines)


def execute_sql_code(user_id: int, sql_text: str, instance_path: str, timeout: int = 5) -> dict:
    """
    Executes SQL statements in an isolated per-user scratch SQLite database.
    Does NOT touch the application database.
    Returns both structured table data and readable ASCII output.
    """
    if not sql_text or not sql_text.strip():
        return {'status': 'success', 'output': '', 'execution_time': 0, 'tables': []}

    scratch_dir = os.path.join(instance_path, 'scratch_sql')
    os.makedirs(scratch_dir, exist_ok=True)
    db_file = os.path.join(scratch_dir, f'editor_user_{user_id}.db')

    statements = split_sql_statements(sql_text)
    if not statements:
        return {'status': 'success', 'output': 'No executable SQL statements found.', 'execution_time': 0, 'tables': []}

    t0 = time.time()
    try:
        conn = sqlite3.connect(db_file, timeout=timeout)
        cursor = conn.cursor()

        messages = []
        tables = []
        ascii_parts = []

        for stmt in statements:
            cursor.execute(stmt)
            if cursor.description:
                cols = [d[0] for d in cursor.description]
                raw_rows = cursor.fetchall()
                clean_rows = []
                for row in raw_rows:
                    clean_rows.append([cell if isinstance(cell, (int, float, str, type(None))) else str(cell) for cell in row])

                tables.append({
                    'columns': cols,
                    'rows': clean_rows,
                    'row_count': len(clean_rows)
                })
                ascii_parts.append(format_ascii_table(cols, clean_rows))
                messages.append(f"Query returned {len(clean_rows)} row(s).")
            else:
                conn.commit()
                if cursor.rowcount >= 0:
                    messages.append(f"Statement executed successfully ({cursor.rowcount} row(s) affected).")
                else:
                    messages.append("Statement executed successfully.")

        elapsed = round(time.time() - t0, 3)
        conn.close()

        final_output = []
        if messages:
            final_output.append("\n".join(messages))
        if ascii_parts:
            final_output.append("\n\n" + "\n\n".join(ascii_parts))

        return {
            'status': 'success',
            'output': "\n".join(final_output).strip() or 'Execution completed successfully.',
            'tables': tables,
            'execution_time': elapsed
        }

    except sqlite3.Error as e:
        elapsed = round(time.time() - t0, 3)
        return {
            'status': 'error',
            'output': f"SQLite Error: {str(e)}",
            'execution_time': elapsed,
            'tables': []
        }
    except Exception as e:
        elapsed = round(time.time() - t0, 3)
        return {
            'status': 'error',
            'output': f"Execution Error: {str(e)}",
            'execution_time': elapsed,
            'tables': []
        }


def reset_user_sql_db(user_id: int, instance_path: str) -> bool:
    """
    Resets the isolated scratch database for the given user.
    """
    scratch_dir = os.path.join(instance_path, 'scratch_sql')
    db_file = os.path.join(scratch_dir, f'editor_user_{user_id}.db')
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            return True
        except Exception:
            return False
    return True
