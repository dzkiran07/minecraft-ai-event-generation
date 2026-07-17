import time
import re
from mcrcon import MCRcon

log_path = "logs/latest.log"

join_pattern = re.compile(r"(\w+) joined the game")
chat_pattern = re.compile(r"<(\w+)> (.+)")
death_pattern = re.compile(r"(\w+) (was slain by|was blown up by|drowned|fell)")

players = {}

LOW_THRESHOLD = 3
HIGH_THRESHOLD = 15
COOLDOWN_SECONDS = 30

def touch_player(name):
       now = time.time()
       if name not in players:
           players[name] = {"session_start": now, "last_active": now, "action_count": 0, "last_event_time": 0}
       players[name]["last_active"] = now
       players[name]["action_count"] += 1

def compute_score(name):
       p = players[name]
       now = time.time()
       idle_time = now - p["last_active"]
       score = (p["action_count"] * 2) - (idle_time * 0.1)
       return round(score, 2), round(idle_time, 1)

def send_command(cmd):
       with MCRcon("localhost", "test123", port=25575) as mcr:
           response = mcr.command(cmd)
           print(f"  -> RCON: {cmd} | response: {response}")

def maybe_trigger_event(name, score):
       p = players[name]
       now = time.time()
       if now - p["last_event_time"] < COOLDOWN_SECONDS:
           return
       if score < LOW_THRESHOLD:
           print(f"[DECISION] {name} is low engagement -> triggering reward event")
           send_command(f"give {name} diamond 3")
           p["last_event_time"] = now
       elif score > HIGH_THRESHOLD:
           print(f"[DECISION] {name} is high engagement -> triggering challenge event")
           send_command(f"execute at {name} run summon minecraft:zombie ~2 ~ ~2")
           p["last_event_time"] = now

with open(log_path, "r", encoding="utf-8") as f:
       f.seek(0, 2)
       while True:
           line = f.readline()
           if not line:
               time.sleep(1)
               continue

           join_match = join_pattern.search(line)
           chat_match = chat_pattern.search(line)
           death_match = death_pattern.search(line)

           name = None
           if join_match:
               name = join_match.group(1)
           elif chat_match:
               name = chat_match.group(1)
           elif death_match:
               name = death_match.group(1)

           if name:
               touch_player(name)
               score, idle = compute_score(name)
               print(f"{name} -> score: {score}  idle: {idle}s")
               maybe_trigger_event(name, score)