import time
import re
import pickle
import csv
import os
from mcrcon import MCRcon

log_path = "../logs/latest.log"

join_pattern = re.compile(r"(\w+) joined the game")
chat_pattern = re.compile(r"<(\w+)> (.+)")
death_pattern = re.compile(r"(\w+) (was slain by|was blown up by|drowned|fell)")

players = {}

LOW_THRESHOLD = 3
HIGH_THRESHOLD = 15
COOLDOWN_SECONDS = 30

# Switch between "rules" and "ml" to compare engines
ENGINE_MODE = "ml"

with open("event_model.pkl", "rb") as f:
    model = pickle.load(f)

session_log_path = "session_log.csv"

if not os.path.exists(session_log_path):
    with open(session_log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "player", "action_count", "idle_time", "session_length", "score", "engine_mode", "decision"])

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

def decide_with_rules(score):
    if score < LOW_THRESHOLD:
        return "reward"
    elif score > HIGH_THRESHOLD:
        return "challenge"
    return "none"

def decide_with_ml(name):
    p = players[name]
    now = time.time()
    idle_time = now - p["last_active"]
    session_length = now - p["session_start"]
    features = [[p["action_count"], idle_time, session_length]]
    return model.predict(features)[0]

def log_to_csv(name, score, decision):
    p = players[name]
    now = time.time()
    idle_time = round(now - p["last_active"], 1)
    session_length = round(now - p["session_start"], 1)
    with open(session_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([round(now, 1), name, p["action_count"], idle_time, session_length, score, ENGINE_MODE, decision])

def maybe_trigger_event(name, score):
    p = players[name]
    now = time.time()
    if now - p["last_event_time"] < COOLDOWN_SECONDS:
        return

    if ENGINE_MODE == "rules":
        decision = decide_with_rules(score)
    else:
        decision = decide_with_ml(name)

    log_to_csv(name, score, decision)

    if decision == "reward":
        print(f"[{ENGINE_MODE.upper()} DECISION] {name} -> reward")
        send_command(f"give {name} diamond 3")
        p["last_event_time"] = now
    elif decision == "challenge":
        print(f"[{ENGINE_MODE.upper()} DECISION] {name} -> challenge")
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