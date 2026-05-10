import threading

GLOBAL_SESSIONS = {}
session_context = threading.local()
