import os
from dotenv import load_dotenv
load_dotenv(".env")

from FiinQuantX import FiinSession

u = os.getenv("FIINQUANT_USERNAME")
p = os.getenv("FIINQUANT_PASSWORD")

print("username set?", bool(u))
print("password set?", bool(p))

client = FiinSession(username=u, password=p).login()

print("client type:", type(client))
print("client dict keys:", list(getattr(client, "__dict__", {}).keys()))
for name in ["is_login", "isLogin", "is_logged_in", "access_token", "token", "session", "client"]:
    try:
        value = getattr(client, name, None)
        if "token" in name.lower():
            print(name, "set?", bool(value))
        else:
            print(name, repr(value))
    except Exception as e:
        print(name, "error", type(e).__name__, str(e))
