from pathlib import Path
import sqlite3

def backup(db_path,destination):
    src=sqlite3.connect(db_path); dst_path=Path(destination); dst_path.parent.mkdir(parents=True,exist_ok=True); dst=sqlite3.connect(dst_path)
    try:src.backup(dst)
    finally:dst.close();src.close()
    return dst_path

def restore(source,db_path):
    src=sqlite3.connect(source); dst=sqlite3.connect(db_path)
    try:src.backup(dst)
    finally:dst.close();src.close()
    return Path(db_path)
