import logging
logger = logging.getLogger("thirdparty.db")

from typing import Any, Dict, List, Tuple

import pyodbc

from utils import try_fix_cp1251_mojibake, normalize_direction, to_hik_mojibake

def db_connect(conn_str: str) -> pyodbc.Connection:
    return pyodbc.connect(conn_str, autocommit=True)

def row_to_dict(cols: List[str], row: Tuple[Any, ...]) -> Dict[str, Any]:
    d = dict(zip(cols, row))
    for k in ("deviceName", "personName", "doorName", "readerName"):
        if k in d:
            d[k] = try_fix_cp1251_mojibake(d[k])
    if "direction" in d:
        d["direction"] = normalize_direction(d["direction"])
    if "authDateTime" in d and hasattr(d["authDateTime"], "strftime"):
        d["authDateTime"] = d["authDateTime"].strftime("%Y-%m-%d %H:%M:%S")
    return d

def get_max_serialno(conn_str: str, table: str) -> int:
    cn = db_connect(conn_str)
    cur = cn.cursor()
    cur.execute(f"SELECT ISNULL(MAX(serialNo), 0) FROM {table}")
    v = cur.fetchone()[0]
    cn.close()
    return int(v or 0)

def get_doors(conn_str: str, table: str) -> List[str]:
    cn = db_connect(conn_str)
    cur = cn.cursor()
    cur.execute(f"""
        SELECT DISTINCT deviceName
        FROM {table}
        WHERE deviceName IS NOT NULL AND LTRIM(RTRIM(deviceName)) <> ''
        ORDER BY deviceName
    """)
    rows = [try_fix_cp1251_mojibake(r[0]) for r in cur.fetchall()]
    cn.close()
    return rows

def build_where(filters: Dict[str, str]) -> Tuple[str, List[Any]]:
    where = []
    params: List[Any] = []

    date_from = filters.get("dateFrom")
    date_to = filters.get("dateTo")
    time_from = filters.get("timeFrom")
    time_to = filters.get("timeTo")
    door = filters.get("door")
    search = filters.get("search")

    if date_from:
        where.append("CAST(authDateTime AS date) >= ?")
        params.append(date_from)
    if date_to:
        where.append("CAST(authDateTime AS date) <= ?")
        params.append(date_to)

    if time_from:
        where.append("CONVERT(time, authDateTime) >= ?")
        params.append(f"{time_from}:00")
    if time_to:
        where.append("CONVERT(time, authDateTime) <= ?")
        params.append(f"{time_to}:59")

    if door and door != "Все":
        door_raw = door
        door_moji = to_hik_mojibake(door)
        where.append("(deviceName = ? OR deviceName = ?)")
        params.extend([door_raw, door_moji])

    if search:
        s = f"%{search}%"
        s_moji = f"%{to_hik_mojibake(search)}%"
        where.append("(personName LIKE ? OR personName LIKE ? OR cardNo LIKE ? OR employeeID LIKE ?)")
        params.extend([s, s_moji, s, s])

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    return where_sql, params

def get_log(conn_str: str, table: str, filters: Dict[str, str], limit: int) -> List[Dict[str, Any]]:
    where_sql, params = build_where(filters)
    sql = f"""
        SELECT TOP {int(limit)}
            serialNo,
            employeeID,
            authDateTime,
            direction,
            deviceName,
            deviceSN,
            personName,
            cardNo,
            doorName,
            readerName
        FROM {table}
        {where_sql}
        ORDER BY serialNo DESC
    """
    cn = db_connect(conn_str)
    cur = cn.cursor()
    cur.execute(sql, params)
    cols = [c[0] for c in cur.description]
    data = [row_to_dict(cols, r) for r in cur.fetchall()]
    cn.close()
    return data

def get_log_after_serial(conn_str: str, table: str, last_serial: int, limit: int) -> List[Dict[str, Any]]:
    sql = f"""
        SELECT TOP {int(limit)}
            serialNo,
            employeeID,
            authDateTime,
            direction,
            deviceName,
            deviceSN,
            personName,
            cardNo,
            doorName,
            readerName
        FROM {table}
        WHERE serialNo > ?
        ORDER BY serialNo ASC
    """
    cn = db_connect(conn_str)
    cur = cn.cursor()
    cur.execute(sql, [last_serial])
    cols = [c[0] for c in cur.description]
    rows = [row_to_dict(cols, r) for r in cur.fetchall()]
    cn.close()
    return rows
