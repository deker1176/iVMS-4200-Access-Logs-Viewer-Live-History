from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils import normalize_direction, parse_dt, format_duration

def compute_summary(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events_sorted = sorted(events, key=lambda x: int(x.get("serialNo", 0)), reverse=True)

    last_by_emp: Dict[str, Dict[str, Any]] = {}
    for e in events_sorted:
        emp = str(e.get("employeeID") or "").strip()
        if not emp:
            continue
        if emp not in last_by_emp:
            last_by_emp[emp] = e

    out = []
    for emp, e in last_by_emp.items():
        d = normalize_direction(e.get("direction"))
        status = "Внутри" if d == "vhod" else ("Снаружи" if d == "vihod" else "Неизвестно")
        out.append({
            "employeeID": emp,
            "personName": e.get("personName") or "",
            "lastAuthDateTime": e.get("authDateTime") or "",
            "lastDirection": d,
            "status": status,
            "lastDeviceName": e.get("deviceName") or "",
            "cardNo": e.get("cardNo") or "",
        })

    out.sort(key=lambda x: (x["personName"], x["employeeID"]))
    return out

def compute_worktime(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_emp: Dict[str, List[Dict[str, Any]]] = {}
    for e in events:
        emp = str(e.get("employeeID") or "").strip()
        if not emp:
            continue
        by_emp.setdefault(emp, []).append(e)

    result = []
    for emp, lst in by_emp.items():
        def e_dt(x):
            return parse_dt(x.get("authDateTime")) or datetime.min

        lst_sorted = sorted(lst, key=e_dt)

        total = timedelta(0)
        first_in: Optional[datetime] = None
        last_out: Optional[datetime] = None
        person_name = ""
        card_no = ""
        open_in: Optional[datetime] = None

        for e in lst_sorted:
            person_name = e.get("personName") or person_name
            card_no = e.get("cardNo") or card_no

            dt = e_dt(e)
            d = normalize_direction(e.get("direction"))

            if d == "vhod":
                if first_in is None:
                    first_in = dt
                open_in = dt
            elif d == "vihod":
                last_out = dt
                if open_in is not None and dt >= open_in:
                    total += (dt - open_in)
                open_in = None

        result.append({
            "employeeID": emp,
            "personName": person_name,
            "cardNo": card_no,
            "firstIn": first_in.strftime("%Y-%m-%d %H:%M:%S") if first_in else "",
            "lastOut": last_out.strftime("%Y-%m-%d %H:%M:%S") if last_out else "",
            "totalInside": format_duration(total),
        })

    result.sort(key=lambda x: (x["personName"], x["employeeID"]))
    return result
